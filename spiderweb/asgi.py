import asyncio
import io
import inspect
import sys
import traceback

from spiderweb.constants import DEFAULT_ENCODING, DEFAULT_ALLOWED_METHODS
from spiderweb.exceptions import NotFound, SpiderwebNetworkException
from spiderweb.response import HttpResponse, JsonResponse, TemplateResponse


def build_environ_from_asgi(scope: dict, body: bytes) -> dict:
    """Convert an ASGI http scope + buffered body into a WSGI-compatible environ."""
    server = scope.get("server") or ("localhost", 8000)
    environ = {
        "REQUEST_METHOD": scope["method"].upper(),
        "SCRIPT_NAME": scope.get("root_path", ""),
        "PATH_INFO": scope["path"],
        "QUERY_STRING": scope.get("query_string", b"").decode("latin1"),
        "SERVER_NAME": server[0],
        "SERVER_PORT": str(server[1]),
        "SERVER_PROTOCOL": f"HTTP/{scope.get('http_version', '1.1')}",
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "wsgi.url_scheme": scope.get("scheme", "http"),
        "GATEWAY_INTERFACE": "CGI/1.1",
    }
    for raw_name, raw_value in scope.get("headers", []):
        name = raw_name.decode("latin1").upper().replace("-", "_")
        value = raw_value.decode("latin1")
        if name == "CONTENT_TYPE":
            environ["CONTENT_TYPE"] = value
        elif name == "CONTENT_LENGTH":
            environ["CONTENT_LENGTH"] = value
        else:
            key = f"HTTP_{name}"
            # Per PEP 3333, repeated headers must be comma-joined (e.g. Cookie, Accept)
            if key in environ:
                environ[key] = environ[key] + ", " + value
            else:
                environ[key] = value
    return environ


class ASGIHandler:
    def __init__(self, router) -> None:
        self._router = router

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
        elif scope["type"] == "http":
            await self._handle_http(scope, receive, send)
        # websocket: not yet handled

    async def _handle_lifespan(self, scope, receive, send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    for cb in getattr(self._router, "on_startup", []):
                        if inspect.iscoroutinefunction(cb):
                            await cb()
                        else:
                            await asyncio.to_thread(cb)
                    await send({"type": "lifespan.startup.complete"})
                except Exception as e:
                    await send({"type": "lifespan.startup.failed", "message": str(e)})
                    return
            elif message["type"] == "lifespan.shutdown":
                try:
                    for cb in getattr(self._router, "on_shutdown", []):
                        if inspect.iscoroutinefunction(cb):
                            await cb()
                        else:
                            await asyncio.to_thread(cb)
                    await send({"type": "lifespan.shutdown.complete"})
                except Exception as e:
                    await send({"type": "lifespan.shutdown.failed", "message": str(e)})
                return

    async def _handle_http(self, scope, receive, send) -> None:
        router = self._router
        max_body = getattr(
            router, "max_request_body_size", 10 * 1024 * 1024
        )  # default 10 MB
        # 1. Buffer request body (enforcing size limit to prevent memory exhaustion)
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if max_body is not None and len(body) > max_body:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"text/plain; charset=utf-8"),
                            (b"connection", b"close"),
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"Request body too large",
                        "more_body": False,
                    }
                )
                return
            if not msg.get("more_body", False):
                break

        # 2. Build environ and Request
        environ = build_environ_from_asgi(scope, body)
        request = router.get_request(environ)

        # 3. Route
        try:
            handler, url_kwargs, allowed_methods = router.get_route(request.path)
        except NotFound:
            handler = router.get_error_route(404)
            url_kwargs = {}
            allowed_methods = DEFAULT_ALLOWED_METHODS
        request.handler = handler

        # Host check first: an invalid host short-circuits before the method check
        # so we don't reveal route/method info to untrusted callers.
        if not router.check_valid_host(request):
            handler = router.get_error_route(403)
        elif request.method not in allowed_methods:
            # RFC 7230: 405 takes priority when the path resolves but the method is wrong.
            handler = router.get_error_route(405)

        # 4. Pre-request middleware (async-aware)
        abort = await router.process_request_middleware_async(request)
        if abort:
            await router.process_response_middleware_async(request, abort)
            await self._send_response(send, request, abort)
            return

        # 5. Dispatch handler (sync or async)
        try:
            if inspect.iscoroutinefunction(handler):
                resp = await handler(request, **url_kwargs)
            else:
                resp = await asyncio.to_thread(handler, request, **url_kwargs)
        except SpiderwebNetworkException as e:
            await self._send_error(send, request, e)
            return

        if resp is None:
            # The ASGI server requires http.response.start before the connection
            # closes. Send a 500 first, then log and return — do NOT raise here.
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"View returned None",
                    "more_body": False,
                }
            )
            router.log.error(f"NoResponseError: view {handler!r} returned None")
            return

        if isinstance(resp, dict):
            resp = JsonResponse(data=resp)
        if isinstance(resp, TemplateResponse):
            resp.set_template_loader(router.template_loader)
            resp.set_string_loader(router.string_loader)

        # 6. Post-request middleware (async-aware)
        await router.process_response_middleware_async(request, resp)

        # 7. Send ASGI response
        await self._send_response(send, request, resp)

    async def _send_response(self, send, request, resp: HttpResponse) -> None:
        router = self._router
        try:
            rendered = resp.render()
            rendered = await router.post_process_middleware_async(
                request, resp, rendered
            )
        except Exception:
            router.log.error(traceback.format_exc())
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"Internal Server Error",
                    "more_body": False,
                }
            )
            return

        if isinstance(rendered, str):
            body_bytes = rendered.encode(DEFAULT_ENCODING)
        elif isinstance(rendered, list):
            body_bytes = b"".join(
                chunk.encode(DEFAULT_ENCODING) if isinstance(chunk, str) else chunk
                for chunk in rendered
            )
        else:
            body_bytes = rendered

        # Normalise headers from a *copy* — never mutate resp.headers so that
        # the response object remains usable if _send_response is called again.
        normalised = {k.replace("_", "-"): v for k, v in resp.headers.items()}
        cookies = normalised.pop("set-cookie", [])
        varies = normalised.pop("vary", [])
        raw_headers = [
            (k.encode("latin1"), str(v).encode("latin1")) for k, v in normalised.items()
        ]
        for c in cookies:
            raw_headers.append((b"set-cookie", str(c).encode("latin1")))
        for v in varies:
            raw_headers.append((b"vary", str(v).encode("latin1")))

        await send(
            {
                "type": "http.response.start",
                "status": resp.status_code,
                "headers": raw_headers,
            }
        )
        await send(
            {"type": "http.response.body", "body": body_bytes, "more_body": False}
        )

    async def _send_error(self, send, request, e: SpiderwebNetworkException) -> None:
        body = f"Something went wrong.\n\nCode: {e.code}\n\nMsg: {e.msg}\n\nDesc: {e.desc}".encode(
            DEFAULT_ENCODING
        )
        status = getattr(e, "code", 500) or 500
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
