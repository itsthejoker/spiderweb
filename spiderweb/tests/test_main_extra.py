"""Extra coverage tests for spiderweb/main.py uncovered branches."""

import sys
import types
from wsgiref.util import setup_testing_defaults

import pytest

from spiderweb import SpiderwebRouter
from spiderweb.exceptions import ServerError
from spiderweb.middleware.base import SpiderwebMiddleware
from spiderweb.response import HttpResponse, TemplateResponse
from spiderweb.tests.helpers import setup


class StartResponse:
    def __init__(self):
        self.status = None
        self.headers = []

    def __call__(self, status, headers):
        self.status = status
        self.headers = headers


def _get_environ(path="/"):
    environ = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = path
    return environ


# ---------------------------------------------------------------------------
# Database setup: no db arg → default path (line 176 branch)
# ---------------------------------------------------------------------------


def test_router_default_db_path(tmp_path, monkeypatch):
    """SpiderwebRouter without db= uses spiderweb.db relative to BASE_DIR."""
    # Patch get_caller_filepath so BASE_DIR points to tmp_path
    monkeypatch.setattr(
        SpiderwebRouter,
        "get_caller_filepath",
        lambda self: tmp_path,
    )
    app = SpiderwebRouter()
    db_path = tmp_path / "spiderweb.db"
    assert db_path.exists()
    app.db_engine.dispose()


def test_router_db_url_string(tmp_path, monkeypatch):
    """db= as a connection URL string uses create_engine (line 172 branch)."""
    monkeypatch.setattr(
        SpiderwebRouter,
        "get_caller_filepath",
        lambda self: tmp_path,
    )
    db_url = f"sqlite:///{tmp_path / 'url.db'}"
    app = SpiderwebRouter(db=db_url)
    # The engine was created from a URL
    assert "sqlite" in str(app.db_engine.url)
    app.db_engine.dispose()


def test_router_db_engine_object(tmp_path, monkeypatch):
    """db= as an already-constructed Engine is used directly (line 168 branch)."""
    from sqlalchemy import create_engine as _create_engine

    monkeypatch.setattr(
        SpiderwebRouter,
        "get_caller_filepath",
        lambda self: tmp_path,
    )
    engine = _create_engine(f"sqlite:///{tmp_path / 'engine.db'}", future=True)
    app = SpiderwebRouter(db=engine)
    assert app.db_engine is engine
    app.db_engine.dispose()


def test_router_media_dir_created_when_missing(tmp_path, monkeypatch):
    """media_dir that doesn't exist is created automatically."""
    monkeypatch.setattr(
        SpiderwebRouter,
        "get_caller_filepath",
        lambda self: tmp_path,
    )
    media_path = tmp_path / "uploads"
    assert not media_path.exists()
    app = SpiderwebRouter(
        db=str(tmp_path / "sw.db"),
        media_dir=str(media_path),
    )
    assert media_path.exists()
    app.db_engine.dispose()


def test_router_media_dir_debug_adds_route(tmp_path, monkeypatch):
    """media_dir + debug=True registers a route for serving media files."""
    from spiderweb.exceptions import NotFound

    monkeypatch.setattr(
        SpiderwebRouter,
        "get_caller_filepath",
        lambda self: tmp_path,
    )
    media_path = tmp_path / "media"
    media_path.mkdir()
    app = SpiderwebRouter(
        db=str(tmp_path / "sw.db"),
        media_dir=str(media_path),
        debug=True,
    )
    try:
        handler, _, _ = app.get_route("/media/somefile.jpg")
        assert handler is not None
    except NotFound:
        pytest.fail("Media route was not registered in debug mode")
    finally:
        app.db_engine.dispose()


# ---------------------------------------------------------------------------
# staticfiles_dirs + debug=True adds static file route (lines 230-239)
# ---------------------------------------------------------------------------


def test_debug_staticfiles_adds_route(tmp_path, monkeypatch):
    """When debug=True and staticfiles_dirs is set, a static route is added."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()

    monkeypatch.setattr(
        SpiderwebRouter,
        "get_caller_filepath",
        lambda self: tmp_path.parent,
    )
    app = SpiderwebRouter(
        db=str(tmp_path / "sw.db"),
        debug=True,
        staticfiles_dirs=[str(static_dir)],
    )
    # A route matching /static/<path> should have been registered
    from spiderweb.exceptions import NotFound

    try:
        handler, _, _ = app.get_route("/static/somefile.txt")
        assert handler is not None
    except NotFound:
        pytest.fail("Static route was not registered in debug mode")
    finally:
        app.db_engine.dispose()


# ---------------------------------------------------------------------------
# fire_response: exception during render → internal error bytes (lines 260-264)
# ---------------------------------------------------------------------------


def test_fire_response_render_exception():
    """If resp.render() raises, fire_response returns an Internal Server Error body."""
    app, environ, _ = setup()

    class _BrokenResponse(HttpResponse):
        def render(self):
            raise RuntimeError("broken render")

    @app.route("/")
    def broken_view(request):
        return _BrokenResponse("irrelevant")

    sr = StartResponse()
    result = app(environ, sr)
    # The server should catch the error and return an Internal Server Error body
    body = b"".join(result)
    assert b"Internal Server Error" in body


# ---------------------------------------------------------------------------
# check_valid_host: missing host header → 403 (line 364)
# ---------------------------------------------------------------------------


def test_check_valid_host_no_host_header():
    """Request with no HTTP_HOST header results in 403."""
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        return HttpResponse("ok")  # pragma: no cover

    # Remove the HTTP_HOST header that setup_testing_defaults would add
    environ.pop("HTTP_HOST", None)

    app(environ, start_response)
    assert start_response.status.startswith("403")


# ---------------------------------------------------------------------------
# check_valid_host: host not in allowed list → 403 (line 368)
# ---------------------------------------------------------------------------


def test_check_valid_host_rejected_host():
    """A host not matching allowed_hosts gets a 403."""
    app, environ, start_response = setup(allowed_hosts=["onlythishost.com"])

    @app.route("/")
    def index(request):
        return HttpResponse("ok")  # pragma: no cover

    environ["HTTP_HOST"] = "evil.example.com"
    app(environ, start_response)
    assert start_response.status.startswith("403")


# ---------------------------------------------------------------------------
# __call__: middleware abort path (line 382+)
# ---------------------------------------------------------------------------


def test_wsgi_middleware_aborts_request():
    """Middleware returning a response from process_request short-circuits the handler."""
    mod_name = "_spiderweb_wsgi_abort_tmp"
    mod = types.ModuleType(mod_name)

    class _AbortMiddleware(SpiderwebMiddleware):
        def process_request(self, request):
            return HttpResponse("blocked", status_code=403)

    mod._AbortMiddleware = _AbortMiddleware
    sys.modules[mod_name] = mod
    try:
        app, environ, start_response = setup(
            middleware=[f"{mod_name}._AbortMiddleware"]
        )

        @app.route("/")
        def index(request):
            return HttpResponse("ok")  # pragma: no cover

        result = app(environ, start_response)
        assert start_response.status.startswith("403")
        assert b"blocked" in b"".join(result)
    finally:
        sys.modules.pop(mod_name, None)


# ---------------------------------------------------------------------------
# __call__: view returns None → NoResponseError propagates
# ---------------------------------------------------------------------------


def test_wsgi_view_returns_none_raises():
    """A view returning None causes NoResponseError to propagate (not caught by WSGI)."""
    from spiderweb.exceptions import NoResponseError

    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        return None  # noqa: RET501  intentional

    with pytest.raises(NoResponseError):
        app(environ, start_response)


# ---------------------------------------------------------------------------
# prepare_and_fire_response: TemplateResponse sets loaders (lines 334-336)
# ---------------------------------------------------------------------------


def test_prepare_and_fire_template_response():
    """TemplateResponse returned from a handler is rendered correctly."""
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        return TemplateResponse(
            request,
            template_string="Hello {{ name }}",
            context={"name": "Spiderweb"},
        )

    result = app(environ, start_response)
    assert b"Hello Spiderweb" in b"".join(result)


# ---------------------------------------------------------------------------
# prepare_and_fire_response: exception in process_response_middleware → 500 fallback
# ---------------------------------------------------------------------------


def test_prepare_and_fire_response_exception_returns_500():
    """An exception in process_response_middleware is caught and returns 500."""
    mod_name = "_spiderweb_pafr_boom_tmp"
    mod = types.ModuleType(mod_name)

    class _BoomResponseMiddleware(SpiderwebMiddleware):
        def process_response(self, request, response):
            raise RuntimeError("response middleware exploded")

    mod._BoomResponseMiddleware = _BoomResponseMiddleware
    sys.modules[mod_name] = mod
    try:
        app, environ, start_response = setup(
            middleware=[f"{mod_name}._BoomResponseMiddleware"]
        )

        @app.route("/")
        def index(request):
            return HttpResponse("ok")

        app(environ, start_response)
        assert start_response.status.startswith("500")
    finally:
        sys.modules.pop(mod_name, None)


# ---------------------------------------------------------------------------
# send_error_response: basic path
# ---------------------------------------------------------------------------


def test_send_error_response_basic():
    """send_error_response writes error details to the response body."""
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        raise ServerError("something broke")

    result = app(environ, start_response)
    body = b"".join(result)
    assert b"Something went wrong" in body
