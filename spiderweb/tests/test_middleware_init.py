"""Tests for the async middleware pipeline in spiderweb/middleware/__init__.py."""

import sys
import types

import httpx
import pytest

from spiderweb.exceptions import UnusedMiddleware
from spiderweb.middleware.base import SpiderwebMiddleware
from spiderweb.response import HttpResponse
from spiderweb.tests.helpers import setup


def _client(asgi_app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=asgi_app),
        base_url="http://testserver",
    )


def _register_middleware(name: str, klass) -> str:
    """Register klass in a temporary sys.modules entry and return the import path."""
    mod = types.ModuleType(name)
    setattr(mod, klass.__name__, klass)
    sys.modules[name] = mod
    return f"{name}.{klass.__name__}"


# ---------------------------------------------------------------------------
# Async process_request_middleware: coroutine function path (line 91)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_process_request_coroutine_middleware():
    """An async process_request middleware is awaited in the async pipeline."""
    executed = []

    class AsyncRequestMiddleware(SpiderwebMiddleware):
        async def process_request(self, request):
            executed.append("async_request")

    path = _register_middleware("_mw_async_req", AsyncRequestMiddleware)
    try:
        app, _, _ = setup(middleware=[path])

        @app.route("/")
        def index(request):
            return HttpResponse("ok")

        async with _client(app.asgi_app) as client:
            resp = await client.get("/")

        assert resp.status_code == 200
        assert "async_request" in executed
    finally:
        sys.modules.pop("_mw_async_req", None)


# ---------------------------------------------------------------------------
# Async process_request_middleware: UnusedMiddleware removal (lines 94-104)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_process_request_unused_middleware_removed():
    """Middleware raising UnusedMiddleware during async request is removed."""

    class UnusedRequestMiddleware(SpiderwebMiddleware):
        def process_request(self, request):
            raise UnusedMiddleware("not needed")

    path = _register_middleware("_mw_unused_req", UnusedRequestMiddleware)
    try:
        app, _, _ = setup(middleware=[path])
        initial_count = len(app.middleware)

        @app.route("/")
        def index(request):
            return HttpResponse("ok")

        async with _client(app.asgi_app) as client:
            resp = await client.get("/")

        assert resp.status_code == 200
        # The middleware should have been removed from the list
        assert len(app.middleware) < initial_count
    finally:
        sys.modules.pop("_mw_unused_req", None)


# ---------------------------------------------------------------------------
# Async process_request_middleware: aborting (returning a response)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_process_request_returns_response_aborts():
    """Async middleware returning a response short-circuits the handler."""

    class AsyncAbortMiddleware(SpiderwebMiddleware):
        async def process_request(self, request):
            return HttpResponse("intercepted", status_code=401)

    path = _register_middleware("_mw_async_abort", AsyncAbortMiddleware)
    try:
        app, _, _ = setup(middleware=[path])

        @app.route("/")
        def index(request):
            return HttpResponse("ok")  # pragma: no cover

        async with _client(app.asgi_app) as client:
            resp = await client.get("/")

        assert resp.status_code == 401
        assert resp.text == "intercepted"
    finally:
        sys.modules.pop("_mw_async_abort", None)


# ---------------------------------------------------------------------------
# Async process_response_middleware: coroutine function path (line 115)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_process_response_coroutine_middleware():
    """An async process_response middleware is awaited in the async pipeline."""
    executed = []

    class AsyncResponseMiddleware(SpiderwebMiddleware):
        async def process_response(self, request, response):
            executed.append("async_response")

    path = _register_middleware("_mw_async_resp", AsyncResponseMiddleware)
    try:
        app, _, _ = setup(middleware=[path])

        @app.route("/")
        def index(request):
            return HttpResponse("ok")

        async with _client(app.asgi_app) as client:
            resp = await client.get("/")

        assert resp.status_code == 200
        assert "async_response" in executed
    finally:
        sys.modules.pop("_mw_async_resp", None)


# ---------------------------------------------------------------------------
# Async process_response_middleware: UnusedMiddleware removal (lines 118-124)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_process_response_unused_middleware_removed():
    """Middleware raising UnusedMiddleware during async response is removed."""

    class UnusedResponseMiddleware(SpiderwebMiddleware):
        def process_response(self, request, response):
            raise UnusedMiddleware("not needed")

    path = _register_middleware("_mw_unused_resp", UnusedResponseMiddleware)
    try:
        app, _, _ = setup(middleware=[path])
        initial_count = len(app.middleware)

        @app.route("/")
        def index(request):
            return HttpResponse("ok")

        async with _client(app.asgi_app) as client:
            resp = await client.get("/")

        assert resp.status_code == 200
        assert len(app.middleware) < initial_count
    finally:
        sys.modules.pop("_mw_unused_resp", None)


# ---------------------------------------------------------------------------
# Async post_process_middleware: coroutine path (line 134)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_post_process_coroutine_middleware():
    """An async post_process middleware is awaited in the async pipeline."""
    executed = []

    class AsyncPostMiddleware(SpiderwebMiddleware):
        async def post_process(self, request, response, rendered):
            executed.append("async_post")
            return rendered

    path = _register_middleware("_mw_async_post", AsyncPostMiddleware)
    try:
        app, _, _ = setup(middleware=[path])

        @app.route("/")
        def index(request):
            return HttpResponse("ok")

        async with _client(app.asgi_app) as client:
            resp = await client.get("/")

        assert resp.status_code == 200
        assert "async_post" in executed
    finally:
        sys.modules.pop("_mw_async_post", None)


# ---------------------------------------------------------------------------
# Async post_process_middleware: UnusedMiddleware removal (lines 137-143)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_post_process_unused_middleware_removed():
    """Middleware raising UnusedMiddleware during async post_process is removed."""

    class UnusedPostMiddleware(SpiderwebMiddleware):
        def post_process(self, request, response, rendered):
            raise UnusedMiddleware("not needed")

    path = _register_middleware("_mw_unused_post", UnusedPostMiddleware)
    try:
        app, _, _ = setup(middleware=[path])
        initial_count = len(app.middleware)

        @app.route("/")
        def index(request):
            return HttpResponse("ok")

        async with _client(app.asgi_app) as client:
            resp = await client.get("/")

        assert resp.status_code == 200
        assert len(app.middleware) < initial_count
    finally:
        sys.modules.pop("_mw_unused_post", None)
