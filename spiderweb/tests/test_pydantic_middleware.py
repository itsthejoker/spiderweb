"""Tests for PydanticMiddleware.

Requires pydantic to be installed (spiderweb-framework[pydantic]).
Skip the whole module gracefully when pydantic is absent.
"""
import sys
import types
from io import BytesIO
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

import pytest

pydantic = pytest.importorskip("pydantic", reason="pydantic not installed")

from spiderweb import SpiderwebRouter
from spiderweb.middleware.pydantic import RequestModel
from spiderweb.response import HttpResponse
from spiderweb.tests.helpers import setup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_environ(fields: dict) -> dict:
    """Return a WSGI environ for a POST request with URL-encoded form data."""
    environ = {}
    setup_testing_defaults(environ)
    body = urlencode(fields).encode()
    environ["REQUEST_METHOD"] = "POST"
    environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    environ["CONTENT_LENGTH"] = str(len(body))
    environ["wsgi.input"] = BytesIO(body)
    environ["HTTP_USER_AGENT"] = "pytest/pydantic"
    environ["REMOTE_ADDR"] = "127.0.0.1"
    return environ


def _get_environ() -> dict:
    environ = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["HTTP_USER_AGENT"] = "pytest/pydantic"
    environ["REMOTE_ADDR"] = "127.0.0.1"
    return environ


class StartResponse:
    def __init__(self):
        self.status = None
        self.headers = []

    def __call__(self, status, headers):
        self.status = status
        self.headers = headers


# ---------------------------------------------------------------------------
# Simple Pydantic model for testing
# ---------------------------------------------------------------------------


class _CommentForm(RequestModel):
    name: str
    comment: str


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pydantic_valid_post_sets_validated_data():
    """Valid POST data is parsed into validated_data on the request."""
    captured = {}

    app, _, _ = setup(
        middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"]
    )

    @app.route("/submit", allowed_methods=["POST"])
    def submit(request: _CommentForm):
        captured["validated"] = request.validated_data
        return HttpResponse("ok")

    sr = StartResponse()
    result = app(_post_environ({"name": "Alice", "comment": "hello"}), sr)

    assert sr.status.startswith("200")
    assert b"ok" in b"".join(result)
    assert captured["validated"].name == "Alice"
    assert captured["validated"].comment == "hello"


def test_pydantic_missing_field_returns_400():
    """POST data missing a required field returns a 400 JSON error."""
    import json

    app, _, _ = setup(
        middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"]
    )

    @app.route("/submit", allowed_methods=["POST"])
    def submit(request: _CommentForm):
        return HttpResponse("should not reach here")  # pragma: no cover

    sr = StartResponse()
    # "comment" is required but not provided
    result = app(_post_environ({"name": "Alice"}), sr)

    assert sr.status.startswith("400")
    body = json.loads(b"".join(result).decode())
    assert body["message"] == "Validation error"
    assert any("comment" in e for e in body["errors"])


def test_pydantic_get_request_skipped():
    """GET requests are not validated — handler is called directly."""
    app, _, _ = setup(
        middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"]
    )

    @app.route("/page")
    def page(request: _CommentForm):
        return HttpResponse("got it")

    sr = StartResponse()
    result = app(_get_environ(), sr)

    assert sr.status.startswith("200")
    assert b"got it" in b"".join(result)


def test_pydantic_unannotated_handler_skipped():
    """A handler without a RequestModel type hint is not validated."""
    app, _, _ = setup(
        middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"]
    )

    @app.route("/plain", allowed_methods=["POST"])
    def plain(request):
        return HttpResponse("plain ok")

    sr = StartResponse()
    result = app(_post_environ({"anything": "goes"}), sr)

    assert sr.status.startswith("200")
    assert b"plain ok" in b"".join(result)


def test_pydantic_server_check_passes_when_installed():
    """CheckPydanticInstalled.check() returns None when pydantic is available."""
    from spiderweb.middleware.pydantic import CheckPydanticInstalled

    check = CheckPydanticInstalled(server=None)
    assert check.check() is None


def test_pydantic_server_check_fails_when_not_installed(monkeypatch):
    """CheckPydanticInstalled.check() returns RuntimeError when pydantic is absent."""
    from spiderweb.middleware.pydantic import CheckPydanticInstalled

    # Temporarily hide pydantic from imports
    pydantic_mod = sys.modules.pop("pydantic", None)
    pydantic_core_mod = sys.modules.pop("pydantic_core", None)
    pydantic_core_inner = sys.modules.pop("pydantic_core._pydantic_core", None)

    try:
        check = CheckPydanticInstalled(server=None)
        result = check.check()
        assert isinstance(result, RuntimeError)
    finally:
        if pydantic_mod is not None:
            sys.modules["pydantic"] = pydantic_mod
        if pydantic_core_mod is not None:
            sys.modules["pydantic_core"] = pydantic_core_mod
        if pydantic_core_inner is not None:
            sys.modules["pydantic_core._pydantic_core"] = pydantic_core_inner


def test_pydantic_multiple_errors_reported():
    """All field errors are included in the 400 response."""
    import json

    class _MultiForm(RequestModel):
        first: str
        second: str
        third: str

    app, _, _ = setup(
        middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"]
    )

    @app.route("/multi", allowed_methods=["POST"])
    def multi(request: _MultiForm):
        return HttpResponse("ok")  # pragma: no cover

    sr = StartResponse()
    # All three fields missing
    result = app(_post_environ({}), sr)

    assert sr.status.startswith("400")
    body = json.loads(b"".join(result).decode())
    assert len(body["errors"]) >= 3
