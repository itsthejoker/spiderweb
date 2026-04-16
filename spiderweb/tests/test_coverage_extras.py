"""Small targeted tests filling remaining coverage gaps across several modules."""

from io import BytesIO

import httpx
import pytest

from spiderweb.tests.helpers import setup, RequestFactory

# ---------------------------------------------------------------------------
# middleware/base.py line 51: SpiderwebMiddleware.on_error default returns None
# ---------------------------------------------------------------------------


def test_middleware_base_on_error_returns_none():
    """The default on_error() implementation returns None."""
    from spiderweb.middleware.base import SpiderwebMiddleware

    mw = object.__new__(SpiderwebMiddleware)
    result = mw.on_error(None, Exception("test"))
    assert result is None


# ---------------------------------------------------------------------------
# middleware/gzip.py line 23: int compression level out of valid range
# ---------------------------------------------------------------------------


def test_gzip_check_int_out_of_range():
    """CheckValidGzipCompressionLevel raises when level is int but out of 1-9."""
    from spiderweb.middleware.gzip import CheckValidGzipCompressionLevel
    from spiderweb.exceptions import ConfigError

    class _Server:
        gzip_compression_level = 0  # valid int, but outside 1-9

    with pytest.raises(ConfigError):
        CheckValidGzipCompressionLevel(server=_Server).check()


# ---------------------------------------------------------------------------
# middleware/csrf.py line 56: trusted origins is not a list
# ---------------------------------------------------------------------------


def test_csrf_verify_trusted_origins_not_a_list():
    """VerifyCorrectFormatForTrustedOrigins.check() errors when origins is not a list."""
    from spiderweb.middleware.csrf import VerifyCorrectFormatForTrustedOrigins
    from spiderweb.exceptions import ConfigError

    class _Server:
        csrf_trusted_origins = "not-a-list"

    check = VerifyCorrectFormatForTrustedOrigins(server=_Server)
    result = check.check()
    assert isinstance(result, ConfigError)


# ---------------------------------------------------------------------------
# middleware/csrf.py line 62: item in list is not a compiled Pattern
# ---------------------------------------------------------------------------


def test_csrf_verify_trusted_origins_item_not_pattern():
    """VerifyCorrectFormatForTrustedOrigins.check() errors when item is a plain string."""
    from spiderweb.middleware.csrf import VerifyCorrectFormatForTrustedOrigins
    from spiderweb.exceptions import ConfigError

    class _Server:
        csrf_trusted_origins = ["plain-string-not-a-pattern"]

    check = VerifyCorrectFormatForTrustedOrigins(server=_Server)
    result = check.check()
    assert isinstance(result, ConfigError)


# ---------------------------------------------------------------------------
# middleware/csrf.py line 133: session key mismatch → is_csrf_valid returns False
# ---------------------------------------------------------------------------


def test_csrf_session_key_mismatch(monkeypatch):
    """is_csrf_valid returns False when the session key in the token doesn't match."""
    from spiderweb.middleware.csrf import CSRFMiddleware

    app, _, _ = setup(
        middleware=[
            "spiderweb.middleware.sessions.SessionMiddleware",
            "spiderweb.middleware.csrf.CSRFMiddleware",
        ]
    )

    # Build a token for a different session_key than what the request will have
    wrong_session_key = "wrong_session_key_12345"
    token = app.encrypt(f"2099-01-01T00:00:00::{wrong_session_key}").decode(
        app.DEFAULT_ENCODING
    )

    mw = CSRFMiddleware(server=app)

    req = RequestFactory.create_request()
    req._session["id"] = "correct_session_key_12345"

    assert mw.is_csrf_valid(req, token) is False


# ---------------------------------------------------------------------------
# request.py line 120: request.json() parses body content
# ---------------------------------------------------------------------------


def test_request_json_method():
    """request.json() returns parsed JSON from the request body."""
    import json
    from wsgiref.util import setup_testing_defaults

    captured = {}

    app, _, _ = setup()

    @app.route("/json-in", allowed_methods=["POST"])
    def json_view(request):
        captured["data"] = request.json()
        from spiderweb.response import HttpResponse

        return HttpResponse("ok")

    environ = {}
    setup_testing_defaults(environ)
    body = json.dumps({"name": "Alice", "value": 42}).encode()
    environ["REQUEST_METHOD"] = "POST"
    environ["CONTENT_TYPE"] = "application/json"
    environ["CONTENT_LENGTH"] = str(len(body))
    environ["wsgi.input"] = BytesIO(body)
    environ["PATH_INFO"] = "/json-in"

    from spiderweb.tests.helpers import StartResponse

    sr = StartResponse()
    app(environ, sr)

    assert captured["data"] == {"name": "Alice", "value": 42}


# ---------------------------------------------------------------------------
# request.py lines 52->exit: form request but method != POST (e.g. GET)
# ---------------------------------------------------------------------------


def test_request_form_get_does_not_parse_post():
    """A form-encoded GET request doesn't populate request.POST."""
    from wsgiref.util import setup_testing_defaults

    environ = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    environ["CONTENT_LENGTH"] = "0"
    environ["wsgi.input"] = BytesIO(b"")

    req = RequestFactory.create_request(environ=environ)
    # POST should remain empty for a GET form request
    assert len(req.POST) == 0


# ---------------------------------------------------------------------------
# asgi.py lines 193, 195: cookies and Vary headers forwarded in ASGI response
# ---------------------------------------------------------------------------


def _asgi_client(asgi_app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=asgi_app),
        base_url="http://testserver",
    )


@pytest.mark.asyncio
async def test_asgi_response_with_cookies():
    """Cookies in the response are forwarded correctly in ASGI mode."""
    from spiderweb.response import HttpResponse

    app, _, _ = setup()

    @app.route("/set-cookie")
    def set_cookie_view(request):
        resp = HttpResponse("hello")
        resp.set_cookie("session", "abc123")
        return resp

    async with _asgi_client(app.asgi_app) as client:
        resp = await client.get("/set-cookie")

    assert resp.status_code == 200
    assert "session" in resp.cookies or "set-cookie" in resp.headers


@pytest.mark.asyncio
async def test_asgi_response_with_vary_header():
    """Vary headers in the response are forwarded correctly in ASGI mode."""
    from spiderweb.response import HttpResponse

    app, _, _ = setup()

    @app.route("/vary")
    def vary_view(request):
        resp = HttpResponse("hello")
        resp.headers["vary"] = ["Accept-Encoding"]
        return resp

    async with _asgi_client(app.asgi_app) as client:
        resp = await client.get("/vary")

    assert resp.status_code == 200
    assert "vary" in resp.headers or "Vary" in resp.headers
