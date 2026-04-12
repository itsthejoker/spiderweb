"""Extra ASGI coverage tests targeting uncovered branches in asgi.py."""

import sys
import types

import httpx
import pytest

from spiderweb.asgi import build_environ_from_asgi
from spiderweb.exceptions import ServerError
from spiderweb.middleware.base import SpiderwebMiddleware
from spiderweb.response import HttpResponse, TemplateResponse
from spiderweb.tests.helpers import setup


def _client(asgi_app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=asgi_app),
        base_url="http://testserver",
    )


# ---------------------------------------------------------------------------
# build_environ_from_asgi unit tests
# ---------------------------------------------------------------------------


def test_build_environ_repeated_headers_joined():
    """Repeated headers should be comma-joined per PEP 3333."""
    scope = {
        "method": "GET",
        "path": "/",
        "headers": [
            (b"cookie", b"a=1"),
            (b"cookie", b"b=2"),
        ],
    }
    environ = build_environ_from_asgi(scope, b"")
    assert environ["HTTP_COOKIE"] == "a=1, b=2"


def test_build_environ_content_type_and_length():
    """content-type and content-length go to their dedicated environ keys."""
    scope = {
        "method": "POST",
        "path": "/",
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", b"42"),
        ],
    }
    environ = build_environ_from_asgi(scope, b'{"x":1}')
    assert environ["CONTENT_TYPE"] == "application/json"
    assert environ["CONTENT_LENGTH"] == "42"
    assert "HTTP_CONTENT_TYPE" not in environ
    assert "HTTP_CONTENT_LENGTH" not in environ


def test_build_environ_default_server():
    """Missing 'server' in scope falls back to localhost:8000."""
    scope = {"method": "GET", "path": "/", "headers": []}
    environ = build_environ_from_asgi(scope, b"")
    assert environ["SERVER_NAME"] == "localhost"
    assert environ["SERVER_PORT"] == "8000"


def test_build_environ_query_string():
    scope = {
        "method": "GET",
        "path": "/search",
        "query_string": b"q=hello&page=1",
        "headers": [],
    }
    environ = build_environ_from_asgi(scope, b"")
    assert environ["QUERY_STRING"] == "q=hello&page=1"


# ---------------------------------------------------------------------------
# HTTP: body too large → 413
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_body_too_large_returns_413():
    app, _, _ = setup()

    @app.route("/upload", allowed_methods=["POST"])
    def upload(request):
        return HttpResponse("ok")  # pragma: no cover

    # Disable the limit so we can control it precisely
    app.max_request_body_size = 10

    async with _client(app.asgi_app) as client:
        resp = await client.post("/upload", content=b"x" * 20)

    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# HTTP: handler raises SpiderwebNetworkException → _send_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_handler_raises_network_exception():
    app, _, _ = setup()

    @app.route("/boom")
    def boom(request):
        raise ServerError("test error")

    async with _client(app.asgi_app) as client:
        resp = await client.get("/boom")

    assert resp.status_code == 500
    assert "test error" in resp.text


# ---------------------------------------------------------------------------
# HTTP: handler returns None → 500 with message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_handler_returns_none():
    app, _, _ = setup()

    @app.route("/none-view")
    def none_view(request):
        return None  # noqa: RET501  intentional for testing

    async with _client(app.asgi_app) as client:
        resp = await client.get("/none-view")

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# HTTP: handler returns a plain dict → JsonResponse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_dict_response():
    app, _, _ = setup()

    @app.route("/data")
    def data_view(request):
        return {"ok": True}

    async with _client(app.asgi_app) as client:
        resp = await client.get("/data")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# ---------------------------------------------------------------------------
# HTTP: TemplateResponse is rendered via asgi app
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_template_response():
    app, _, _ = setup()

    @app.route("/tmpl")
    def tmpl_view(request):
        return TemplateResponse(
            request, template_string="hello {{ name }}", context={"name": "world"}
        )

    async with _client(app.asgi_app) as client:
        resp = await client.get("/tmpl")

    assert resp.status_code == 200
    assert "hello world" in resp.text


# ---------------------------------------------------------------------------
# HTTP: invalid host → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_invalid_host_returns_403():
    app, _, _ = setup(allowed_hosts=["onlythishost.com"])

    @app.route("/secret")
    def secret(request):
        return HttpResponse("secret")  # pragma: no cover

    async with _client(app.asgi_app) as client:
        resp = await client.get("/secret", headers={"host": "evil.example.com"})

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# HTTP: middleware aborts request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_middleware_abort():
    """Middleware returning a response short-circuits the handler."""
    mod_name = "_spiderweb_abort_mw_tmp"
    mod = types.ModuleType(mod_name)

    class AbortMiddleware(SpiderwebMiddleware):
        def process_request(self, request):
            return HttpResponse("aborted", status_code=403)

    mod.AbortMiddleware = AbortMiddleware
    sys.modules[mod_name] = mod
    try:
        app, _, _ = setup(middleware=[f"{mod_name}.AbortMiddleware"])

        @app.route("/protected")
        def protected(request):
            return HttpResponse("secret")  # pragma: no cover

        async with _client(app.asgi_app) as client:
            resp = await client.get("/protected")

        assert resp.status_code == 403
        assert resp.text == "aborted"
    finally:
        sys.modules.pop(mod_name, None)


# ---------------------------------------------------------------------------
# Lifespan: async startup and shutdown callbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_lifespan_async_callbacks():
    """Async on_startup and on_shutdown callbacks are awaited correctly."""
    called = []

    async def async_startup():
        called.append("startup")

    async def async_shutdown():
        called.append("shutdown")

    from spiderweb import SpiderwebRouter

    app = SpiderwebRouter(
        db="spiderweb-tests.db",
        on_startup=[async_startup],
        on_shutdown=[async_shutdown],
    )
    handler = app.asgi_app

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


# ---------------------------------------------------------------------------
# Lifespan: startup callback raises → lifespan.startup.failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_lifespan_startup_failure():
    """A raising startup callback sends lifespan.startup.failed."""
    from spiderweb import SpiderwebRouter

    def bad_startup():
        raise RuntimeError("startup exploded")

    app = SpiderwebRouter(
        db="spiderweb-tests.db",
        on_startup=[bad_startup],
    )
    handler = app.asgi_app

    messages = [{"type": "lifespan.startup"}]
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
    assert any(m["type"] == "lifespan.startup.failed" for m in sent)
    failed = next(m for m in sent if m["type"] == "lifespan.startup.failed")
    assert "startup exploded" in failed["message"]


# ---------------------------------------------------------------------------
# Lifespan: shutdown callback raises → lifespan.shutdown.failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_lifespan_shutdown_failure():
    """A raising shutdown callback sends lifespan.shutdown.failed."""
    from spiderweb import SpiderwebRouter

    def bad_shutdown():
        raise RuntimeError("shutdown exploded")

    app = SpiderwebRouter(
        db="spiderweb-tests.db",
        on_shutdown=[bad_shutdown],
    )
    handler = app.asgi_app

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
    assert any(m["type"] == "lifespan.shutdown.failed" for m in sent)
    failed = next(m for m in sent if m["type"] == "lifespan.shutdown.failed")
    assert "shutdown exploded" in failed["message"]


# ---------------------------------------------------------------------------
# _send_response: render raises → 500
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asgi_send_response_render_error():
    """An exception during response.render() causes a 500."""
    app, _, _ = setup()

    class _BrokenResponse(HttpResponse):
        def render(self):
            raise RuntimeError("render exploded")

    @app.route("/broken")
    def broken_view(request):
        return _BrokenResponse("irrelevant")

    async with _client(app.asgi_app) as client:
        resp = await client.get("/broken")

    assert resp.status_code == 500
