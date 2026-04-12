import sys
import types

import httpx
import pytest

from spiderweb import SpiderwebRouter
from spiderweb.middleware.base import SpiderwebMiddleware
from spiderweb.response import HttpResponse, JsonResponse
from spiderweb.tests.helpers import setup


def _client(asgi_app):
    """Return an httpx.AsyncClient wired to *asgi_app* via ASGITransport."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=asgi_app),
        base_url="http://testserver",
    )


@pytest.mark.asyncio
async def test_asgi_basic_get():
    app, _, _ = setup()

    @app.route("/hello")
    def hello(request):
        return HttpResponse("world")

    async with _client(app.asgi_app) as client:
        resp = await client.get("/hello")
    assert resp.status_code == 200
    assert resp.text == "world"


@pytest.mark.asyncio
async def test_asgi_async_handler():
    app, _, _ = setup()

    @app.route("/async")
    async def async_view(request):
        return HttpResponse("async ok")

    async with _client(app.asgi_app) as client:
        resp = await client.get("/async")
    assert resp.status_code == 200
    assert resp.text == "async ok"


@pytest.mark.asyncio
async def test_asgi_404():
    app, _, _ = setup()
    async with _client(app.asgi_app) as client:
        resp = await client.get("/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_asgi_json_response():
    app, _, _ = setup()

    @app.route("/json")
    def json_view(request):
        return JsonResponse(data={"key": "value"})

    async with _client(app.asgi_app) as client:
        resp = await client.get("/json")
    assert resp.status_code == 200
    assert resp.json() == {"key": "value"}


@pytest.mark.asyncio
async def test_asgi_post_body():
    app, _, _ = setup()

    @app.route("/echo", allowed_methods=["POST"])
    def echo(request):
        return HttpResponse(request.content)

    async with _client(app.asgi_app) as client:
        resp = await client.post("/echo", content=b"hello body")
    assert resp.status_code == 200
    assert resp.text == "hello body"


@pytest.mark.asyncio
async def test_asgi_405_wrong_method():
    app, _, _ = setup()

    @app.route("/post-only", allowed_methods=["POST"])
    def post_only(request):
        return HttpResponse("ok")

    async with _client(app.asgi_app) as client:
        resp = await client.get("/post-only")
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_asgi_middleware_sync_and_async():
    """Sync and async middleware both execute in ASGI mode."""
    executed = []

    class SyncMiddleware(SpiderwebMiddleware):
        def process_request(self, request):
            executed.append("sync")

    class AsyncMiddleware(SpiderwebMiddleware):
        async def process_request(self, request):
            executed.append("async")

    # Middleware must be registered by import string. Use a throwaway module
    # registered in sys.modules so no existing namespace is polluted.
    mod_name = "_spiderweb_test_mw_tmp"
    mod = types.ModuleType(mod_name)
    mod.SyncMiddleware = SyncMiddleware
    mod.AsyncMiddleware = AsyncMiddleware
    sys.modules[mod_name] = mod
    try:
        app, _, _ = setup(
            middleware=[
                f"{mod_name}.SyncMiddleware",
                f"{mod_name}.AsyncMiddleware",
            ]
        )

        @app.route("/mw-test")
        def view(request):
            return HttpResponse("ok")

        async with _client(app.asgi_app) as client:
            resp = await client.get("/mw-test")

        assert resp.status_code == 200
        assert "sync" in executed
        assert "async" in executed
    finally:
        sys.modules.pop(mod_name, None)


@pytest.mark.asyncio
async def test_asgi_lifespan_callbacks():
    """on_startup and on_shutdown callbacks are invoked."""
    called = []
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

    # Touch asgi_app to trigger cached_property creation — regression scenario:
    # does WSGI still work after the ASGI handler has been instantiated?
    _ = app.asgi_app

    environ["PATH_INFO"] = "/wsgi-check"
    environ["REQUEST_METHOD"] = "GET"
    body_iter = app(environ, start_response)
    assert start_response.status.startswith("200")
    assert b"".join(body_iter) == b"wsgi ok"
