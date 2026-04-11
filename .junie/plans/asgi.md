# ASGI Support Plan for Spiderweb

## 1. Goals and Non-Goals

### Goals
- Add an ASGI-compatible entry point alongside the existing WSGI `__call__`; existing WSGI apps continue to work unchanged.
- Allow view handlers to be `async def`; async handlers run natively via `await` in ASGI mode, and run via `asyncio.to_thread()` in WSGI mode if needed in the future.
- Allow middleware to optionally define `async def process_request`, `async def process_response`, and `async def post_process`; the dispatcher detects and awaits them.
- Support the ASGI `lifespan` scope for startup/shutdown hooks.
- Provide an ASGI-capable dev server (uvicorn-based) via `app.start_asgi()`.
- Keep the existing `SpiderwebRouter` class as the single source of truth — no forking the class hierarchy.

### Non-Goals
- WebSocket support (deferred to a future plan).
- Converting the internal database layer to async (SQLAlchemy `AsyncSession`); sync DB access continues via `asyncio.to_thread()` for now.
- Deprecating WSGI. Both protocols must work simultaneously with the same `SpiderwebRouter` instance.

---

## 2. Background: Current Architecture

`SpiderwebRouter` is a standard synchronous WSGI application:

```
WSGI server → SpiderwebRouter.__call__(environ, start_response)
              → get_request(environ)           → Request
              → get_route(path)                → (handler, url_kwargs, allowed_methods)
              → process_request_middleware()   → possible short-circuit response
              → handler(request, **url_kwargs) → HttpResponse
              → process_response_middleware()
              → fire_response()               → start_response() + list[bytes]
```

The `Request` class is constructed entirely from the WSGI `environ` dict. All middleware methods (`process_request`, `process_response`, `post_process`) are synchronous. The dev server is `wsgiref.simple_server.WSGIServer`.

---

## 3. Design Decisions

### 3.1 Single Class, Two Protocols

`SpiderwebRouter` keeps its synchronous `__call__(self, environ, start_response)` as-is for WSGI. A new `asgi_app` property (returning an `ASGIHandler` bound to that router instance) exposes the ASGI interface. Users opt in to ASGI explicitly:

```python
# WSGI (unchanged)
app = SpiderwebRouter(...)
wsgi_app = app                  # pass to gunicorn, wsgiref, etc.

# ASGI (opt-in)
asgi_app = app.asgi_app         # pass to uvicorn, hypercorn, etc.
```

### 3.2 The Environ Bridge — Reuse `Request` Unchanged

The ASGI `http` scope carries the same semantic information as a WSGI `environ`. Rather than rewriting `Request`, we build a WSGI-compatible `environ` dict from the ASGI scope + buffered body. This isolates all ASGI-specific logic to `spiderweb/asgi.py` and keeps `Request`, routing, and middleware totally unaware of the protocol.

```python
# ASGI scope ──► build_environ_from_asgi(scope, body) ──► dict
#   method, path, headers, query_string, scheme, server
#   + wsgi.input = io.BytesIO(body)
#   + wsgi.errors, wsgi.url_scheme, etc.
```

### 3.3 Async Handler Dispatch

Inside `ASGIHandler.handle_http`, after routing, handler dispatch becomes:

```python
import asyncio, inspect

if inspect.iscoroutinefunction(handler):
    resp = await handler(request, **url_kwargs)
else:
    resp = await asyncio.to_thread(handler, request, **url_kwargs)
```

This means any existing sync handler works in ASGI mode with zero changes, and new `async def` handlers work natively.

### 3.4 Async Middleware Dispatch

`MiddlewareMixin` gains three async counterparts to its existing sync dispatch methods. Each method checks `asyncio.iscoroutinefunction` on every middleware's hook before deciding to `await` or `asyncio.to_thread`:

```python
async def process_request_middleware_async(self, request) -> HttpResponse | None: ...
async def process_response_middleware_async(self, request, response) -> None: ...
async def post_process_middleware_async(self, request, response, rendered) -> str: ...
```

The original sync methods are **not modified**; they remain for WSGI. Middleware authors who want native async performance define `async def process_request(...)` instead of `def process_request(...)`. Sync middleware is always safe to use in both modes.

### 3.5 ASGI Response Sending

After getting back an `HttpResponse` (sync or async-rendered), `ASGIHandler` converts it to two ASGI messages:

```python
await send({"type": "http.response.start", "status": resp.status_code, "headers": [...]})
await send({"type": "http.response.body", "body": body_bytes, "more_body": False})
```

`FileResponse` streaming is a special case: if the response has a `file` attribute, chunks are sent with `more_body=True` until exhausted.

### 3.6 Lifespan

`ASGIHandler` handles `lifespan` scope to drive startup/shutdown callbacks registered on the router. The router gains two new optional lists: `on_startup: list[Callable]` and `on_shutdown: list[Callable]`, which default to empty lists (no-ops in current WSGI usage).

### 3.7 No New Hard Dependencies

`uvicorn` is added as an **optional** dependency under the `[asgi]` extra. No mandatory new deps are introduced. The `ASGIHandler` itself has no imports beyond the stdlib (`asyncio`, `io`, `sys`) and existing spiderweb modules.

---

## 4. Phased Implementation

### Phase 1 — Core ASGI HTTP Handler (minimum viable)

**New file: `spiderweb/asgi.py`**

```python
import asyncio
import io
import inspect
import sys
import traceback
from typing import Callable

from spiderweb.constants import DEFAULT_ENCODING, DEFAULT_ALLOWED_METHODS
from spiderweb.exceptions import NotFound, SpiderwebNetworkException, NoResponseError
from spiderweb.response import HttpResponse, JsonResponse, TemplateResponse
from spiderweb.utils import get_http_status_by_code


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
    def __init__(self, router):
        self._router = router

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
        elif scope["type"] == "http":
            await self._handle_http(scope, receive, send)
        # websocket: not yet handled

    async def _handle_lifespan(self, scope, receive, send):
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

    async def _handle_http(self, scope, receive, send):
        router = self._router
        max_body = getattr(router, "max_request_body_size", 10 * 1024 * 1024)  # default 10 MB
        # 1. Buffer request body (enforcing size limit to prevent memory exhaustion)
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if max_body is not None and len(body) > max_body:
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                                        (b"connection", b"close")]})
                await send({"type": "http.response.body",
                            "body": b"Request body too large", "more_body": False})
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
            # Raising after send() would propagate an unhandled exception to the
            # ASGI server even though the client already received a valid response,
            # triggering spurious server-level error handling.
            await send({"type": "http.response.start", "status": 500,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
            await send({"type": "http.response.body",
                        "body": b"View returned None", "more_body": False})
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

    async def _send_response(self, send, request, resp: HttpResponse):
        router = self._router
        try:
            rendered = resp.render()
            rendered = await router.post_process_middleware_async(request, resp, rendered)
        except Exception:
            router.log.error(traceback.format_exc())
            # Send a proper 500 immediately; do NOT fall through with the original
            # resp.status_code, which could be 200, producing a misleading response.
            await send({"type": "http.response.start", "status": 500,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
            await send({"type": "http.response.body", "body": b"Internal Server Error",
                        "more_body": False})
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
        # the response object remains usable if _send_response is called again
        # (e.g. in a logging or retry path added in the future).
        normalised = {k.replace("_", "-"): v for k, v in resp.headers.items()}
        cookies = normalised.pop("set-cookie", [])
        varies = normalised.pop("vary", [])
        raw_headers = [(k.encode("latin1"), str(v).encode("latin1")) for k, v in normalised.items()]
        for c in cookies:
            raw_headers.append((b"set-cookie", str(c).encode("latin1")))
        for v in varies:
            raw_headers.append((b"vary", str(v).encode("latin1")))

        await send({"type": "http.response.start", "status": resp.status_code, "headers": raw_headers})
        await send({"type": "http.response.body", "body": body_bytes, "more_body": False})

    async def _send_error(self, send, request, e: SpiderwebNetworkException):
        body = f"Something went wrong.\n\nCode: {e.code}\n\nMsg: {e.msg}\n\nDesc: {e.desc}".encode(DEFAULT_ENCODING)
        # Use the exception's own status code, not a hardcoded 500.
        status = getattr(e, "code", 500) or 500
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
        await send({"type": "http.response.body", "body": body, "more_body": False})
```

**Changes to `spiderweb/middleware/__init__.py`** — add three async dispatch methods:

```python
async def process_request_middleware_async(self, request):
    # Iterate over a snapshot so removals during the loop don't skip elements.
    # Do NOT call process_response_middleware_async here — the caller (_handle_http)
    # is responsible for running response middleware on the abort response.
    # Calling it here and in the caller would run response middleware twice.
    to_remove = []
    result = None
    for middleware in list(self.middleware):
        try:
            fn = middleware.process_request
            if inspect.iscoroutinefunction(fn):
                resp = await fn(request)
            else:
                resp = await asyncio.to_thread(fn, request)
        except UnusedMiddleware:
            to_remove.append(middleware)
            continue
        if resp:
            result = resp
            break
    # Apply removals after the loop. Guard against ValueError in case a
    # concurrent coroutine already removed the same middleware.
    for m in to_remove:
        try:
            self.middleware.remove(m)
        except ValueError:
            pass
    return result  # caller handles process_response_middleware_async

async def process_response_middleware_async(self, request, response):
    to_remove = []
    for middleware in list(reversed(self.middleware)):
        try:
            fn = middleware.process_response
            if inspect.iscoroutinefunction(fn):
                await fn(request, response)
            else:
                await asyncio.to_thread(fn, request, response)
        except UnusedMiddleware:
            to_remove.append(middleware)
    for m in to_remove:
        try:
            self.middleware.remove(m)
        except ValueError:
            pass

async def post_process_middleware_async(self, request, response, rendered):
    to_remove = []
    for middleware in list(reversed(self.middleware)):
        try:
            fn = middleware.post_process
            if inspect.iscoroutinefunction(fn):
                rendered = await fn(request, response, rendered)
            else:
                rendered = await asyncio.to_thread(fn, request, response, rendered)
        except UnusedMiddleware:
            to_remove.append(middleware)
    for m in to_remove:
        try:
            self.middleware.remove(m)
        except ValueError:
            pass
    return rendered
```

**Changes to `spiderweb/main.py`**:

```python
# Add to __init__ parameters:
on_startup: list[Callable] = None,
on_shutdown: list[Callable] = None,
max_request_body_size: int | None = 10 * 1024 * 1024,  # 10 MB; None disables the limit

# Add to __init__ body:
self.on_startup = on_startup or []
self.on_shutdown = on_shutdown or []
self.max_request_body_size = max_request_body_size

# Also update the existing WSGI __call__ to match the ASGI host/method check
# ordering (host first, method second via elif). The current WSGI path runs
# method check first, then host check, which means the same router behaves
# differently under WSGI vs ASGI for a request that fails both checks.
# Fixing __call__ here keeps both protocols consistent.
#
# Existing WSGI (to be updated):
#   if request.method not in allowed_methods:
#       handler = self.get_error_route(405)
#   if not self.check_valid_host(request):
#       handler = self.get_error_route(403)
#
# Replacement:
#   if not self.check_valid_host(request):
#       handler = self.get_error_route(403)
#   elif request.method not in allowed_methods:
#       handler = self.get_error_route(405)
```

# Add as cached_property so repeated access returns the same instance —
# avoids allocating a new ASGIHandler on every attribute read and ensures
# the lifespan scope always interacts with the same handler object as HTTP requests.
import functools

@functools.cached_property
def asgi_app(self):
    from spiderweb.asgi import ASGIHandler
    return ASGIHandler(self)
```

**Changes to `spiderweb/__init__.py`** — export `ASGIHandler` for convenience.

**Changes to `pyproject.toml`**:

```toml
[project.optional-dependencies]
pydantic = ["pydantic>=2.8.2,<3"]
asgi = ["uvicorn>=0.30.0"]
```

Also add `pytest-asyncio>=0.24.0` to the `dev` dependency group for async test support.

---

### Phase 2 — ASGI Dev Server

**Changes to `spiderweb/local_server.py`** — add `start_asgi()` to `LocalServerMixin`:

Add `import asyncio` and `import threading` at the top of `local_server.py` — both are used by `start_asgi()` and are not currently imported there.

```python
# New imports at the top of local_server.py:
import asyncio
import threading

def start_asgi(self, blocking=True):
    try:
        import uvicorn
    except ImportError:
        raise ConfigError(
            "uvicorn is required for ASGI mode. "
            "Install it with: pip install spiderweb-framework[asgi]"
        )
    self.log.info(f"Starting ASGI server on http://{self.addr}:{self.port}")
    self.log.info("Press CTRL+C to stop the server.")
    # Do NOT call signal.signal() here: uvicorn installs its own SIGINT/SIGTERM
    # handlers and would immediately overwrite ours. Shutdown hooks should be
    # registered via on_shutdown= callbacks instead.
    #
    # NOTE: asyncio.run() raises RuntimeError if an event loop is already running
    # (e.g. inside pytest-asyncio tests or Jupyter). In those environments, call
    # app.asgi_app directly with an external ASGI server instead of start_asgi().
    config = uvicorn.Config(self.asgi_app, host=self.addr, port=self.port)
    server = uvicorn.Server(config)
    if blocking:
        # Blocks the calling thread until the server exits (mirrors start(blocking=True))
        asyncio.run(server.serve())
    else:
        # Run the server in a background thread and return immediately
        # (mirrors the threading behaviour of start(blocking=False))
        t = threading.Thread(target=asyncio.run, args=(server.serve(),), daemon=True)
        t.start()
        return t
```

---

### Phase 3 — Tests

**New file: `spiderweb/tests/test_asgi.py`**

Tests use `httpx` with its `AsyncClient` in ASGI transport mode (no server needed):

```python
import pytest
import httpx
from spiderweb.response import HttpResponse, JsonResponse
from spiderweb.tests.helpers import setup

@pytest.mark.asyncio
async def test_asgi_basic_get():
    app, _, _ = setup()

    @app.route("/hello")
    def hello(request):
        return HttpResponse("world")

    async with httpx.AsyncClient(app=app.asgi_app, base_url="http://testserver") as client:
        resp = await client.get("/hello")
    assert resp.status_code == 200
    assert resp.text == "world"

@pytest.mark.asyncio
async def test_asgi_async_handler():
    app, _, _ = setup()

    @app.route("/async")
    async def async_view(request):
        return HttpResponse("async ok")

    async with httpx.AsyncClient(app=app.asgi_app, base_url="http://testserver") as client:
        resp = await client.get("/async")
    assert resp.status_code == 200
    assert resp.text == "async ok"

@pytest.mark.asyncio
async def test_asgi_404():
    app, _, _ = setup()
    async with httpx.AsyncClient(app=app.asgi_app, base_url="http://testserver") as client:
        resp = await client.get("/nonexistent")
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_asgi_json_response():
    app, _, _ = setup()

    @app.route("/json")
    def json_view(request):
        return JsonResponse(data={"key": "value"})

    async with httpx.AsyncClient(app=app.asgi_app, base_url="http://testserver") as client:
        resp = await client.get("/json")
    assert resp.status_code == 200
    assert resp.json() == {"key": "value"}

@pytest.mark.asyncio
async def test_asgi_post_body():
    app, _, _ = setup()

    @app.route("/echo", allowed_methods=["POST"])
    def echo(request):
        return HttpResponse(request.content)

    async with httpx.AsyncClient(app=app.asgi_app, base_url="http://testserver") as client:
        resp = await client.post("/echo", content=b"hello body")
    assert resp.status_code == 200
    assert resp.text == "hello body"

@pytest.mark.asyncio
async def test_asgi_middleware_sync_and_async():
    """Sync and async middleware both execute in ASGI mode."""
    import sys
    import types
    from spiderweb.middleware.base import SpiderwebMiddleware

    executed = []

    class SyncMiddleware(SpiderwebMiddleware):
        def process_request(self, request):
            executed.append("sync")

    class AsyncMiddleware(SpiderwebMiddleware):
        async def process_request(self, request):
            executed.append("async")

    # Middleware must be registered by import string. Use a throwaway module
    # registered in sys.modules under a test-local name so no existing namespace
    # is polluted, and tear it down unconditionally in the finally block.
    mod_name = "_spiderweb_test_mw_tmp"
    mod = types.ModuleType(mod_name)
    mod.SyncMiddleware = SyncMiddleware
    mod.AsyncMiddleware = AsyncMiddleware
    sys.modules[mod_name] = mod
    try:
        app, _, _ = setup(middleware=[
            f"{mod_name}.SyncMiddleware",
            f"{mod_name}.AsyncMiddleware",
        ])

        @app.route("/mw-test")
        def view(request):
            return HttpResponse("ok")

        async with httpx.AsyncClient(app=app.asgi_app, base_url="http://testserver") as client:
            resp = await client.get("/mw-test")

        assert resp.status_code == 200
        assert "sync" in executed
        assert "async" in executed
    finally:
        sys.modules.pop(mod_name, None)

@pytest.mark.asyncio
async def test_asgi_lifespan_callbacks():
    """on_startup and on_shutdown callbacks are invoked."""
    # helpers.setup() doesn't forward on_startup/on_shutdown; construct directly.
    called = []
    from spiderweb import SpiderwebRouter
    app = SpiderwebRouter(
        db="spiderweb-tests.db",
        on_startup=[lambda: called.append("startup")],
        on_shutdown=[lambda: called.append("shutdown")],
    )
    handler = app.asgi_app
    # Drive the lifespan protocol manually.
    messages = [
        {"type": "lifespan.startup"},
        {"type": "lifespan.shutdown"},
    ]
    sent = []
    idx = 0

    async def receive():
        nonlocal idx
        msg = messages[idx]
        idx += 1
        return msg

    async def send(msg):
        sent.append(msg)

    await handler({"type": "lifespan"}, receive, send)
    assert "startup" in called
    assert "shutdown" in called
    assert any(m["type"] == "lifespan.startup.complete" for m in sent)
    assert any(m["type"] == "lifespan.shutdown.complete" for m in sent)

@pytest.mark.asyncio
async def test_wsgi_still_works_alongside_asgi():
    """Existing WSGI __call__ continues to function after asgi_app is accessed."""
    app, environ, start_response = setup()

    @app.route("/wsgi-check")
    def wsgi_view(request):
        return HttpResponse("wsgi ok")

    # Touch asgi_app to trigger cached_property creation — this is the regression
    # scenario: does WSGI still work after the ASGI handler has been instantiated?
    _ = app.asgi_app

    environ["PATH_INFO"] = "/wsgi-check"
    environ["REQUEST_METHOD"] = "GET"
    body_iter = app(environ, start_response)
    assert start_response.status.startswith("200")
    assert b"".join(body_iter) == b"wsgi ok"
```

Add `httpx>=0.27.0` and `pytest-asyncio>=0.24.0` to the `dev` dependency group.

Add `asyncio_mode = "strict"` to `[tool.pytest.ini_options]` in `pyproject.toml`. Do **not** use `"auto"` — that would wrap every test function (including all existing sync WSGI tests) in an event loop, which can cause subtle failures in tests that instantiate `SpiderwebRouter` in ways that interact badly with a running event loop. With `"strict"`, only tests explicitly decorated with `@pytest.mark.asyncio` run in async mode.

---

## 5. File-by-File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `spiderweb/asgi.py` | **New** | `ASGIHandler`, `build_environ_from_asgi` |
| `spiderweb/main.py` | Modify | Add `on_startup`, `on_shutdown`, `max_request_body_size` params; add `asgi_app` cached property; align host/method check order in WSGI `__call__` to match ASGI |
| `spiderweb/middleware/__init__.py` | Modify | Add `process_request_middleware_async`, `process_response_middleware_async`, `post_process_middleware_async` |
| `spiderweb/local_server.py` | Modify | Add `import asyncio`, `import threading`; add `start_asgi()` to `LocalServerMixin` |
| `spiderweb/__init__.py` | Modify | Export `ASGIHandler` |
| `spiderweb/tests/test_asgi.py` | **New** | ASGI-specific test suite |
| `pyproject.toml` | Modify | Add `[asgi]` optional dep, add `httpx` + `pytest-asyncio` to dev deps |

**No changes required to:**
- `spiderweb/request.py` — `Request` works unchanged via the environ bridge
- `spiderweb/response.py` — `HttpResponse` and subclasses are unmodified
- `spiderweb/middleware/base.py` — `SpiderwebMiddleware` remains the base; async methods are optional additions users can define
- All existing middleware — they continue to work synchronously in both WSGI and ASGI modes

---

## 6. Backward-Compatibility Guarantees

- `SpiderwebRouter.__call__(environ, start_response)` is not touched.
- `SpiderwebRouter.start()` continues to use `wsgiref` as before.
- No existing public API is changed or removed.
- `on_startup` and `on_shutdown` default to empty lists and are no-ops in WSGI mode.
- `asgi_app` is a `cached_property`; it returns the **same** `ASGIHandler` instance on every access. Pass `app.asgi_app` to uvicorn/hypercorn once and reuse freely.

---

## 7. Known Limitations and Future Work

- **WebSocket**: Not addressed. A `websocket` scope handler can be added to `ASGIHandler.__call__` in a follow-up.
- **Async DB access**: Database access (sessions, etc.) in built-in middleware is still synchronous; it runs via `asyncio.to_thread` in ASGI mode. A future plan can introduce SQLAlchemy `AsyncSession` support.
- **Streaming responses**: `FileResponse` currently buffers the entire file. True async streaming (multiple `more_body=True` chunks) is deferred.
- **HTTP/2 and HTTP/3**: Transparent via the ASGI server (uvicorn, hypercorn); no changes needed in spiderweb itself.
- **Middleware async by default**: All built-in middleware (`SessionMiddleware`, `CsrfMiddleware`, etc.) remain sync. They execute via `asyncio.to_thread` in ASGI mode. Authors of third-party middleware can opt into native async by defining `async def` hooks.

---

## 8. Example Usage After Implementation

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse

app = SpiderwebRouter(
    on_startup=[lambda: print("App started")],
    on_shutdown=[lambda: print("App stopped")],
)

@app.route("/")
def index(request):
    return HttpResponse("Hello from WSGI or ASGI!")

@app.route("/async-only")
async def async_view(request):
    # native async handler — only beneficial in ASGI mode
    return HttpResponse("async response")

# WSGI usage (unchanged):
# gunicorn example:app
# or: app.start()

# ASGI usage:
# uvicorn example:app.asgi_app
# or: app.start_asgi()
```
