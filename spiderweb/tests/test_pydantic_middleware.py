"""Tests for PydanticMiddleware.

Requires pydantic to be installed (spiderweb-framework[pydantic]).
Skip the whole module gracefully when pydantic is absent.
"""

import json
from io import BytesIO
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

import pytest

from spiderweb.middleware.pydantic import RequestModel
from spiderweb.response import HttpResponse
from spiderweb.tests.helpers import StartResponse, setup

pydantic = pytest.importorskip("pydantic", reason="pydantic not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_environ(fields: dict, path: str = "/") -> dict:
    """Return a WSGI environ for a POST request with URL-encoded form data."""
    environ = {}
    setup_testing_defaults(environ)
    body = urlencode(fields).encode()
    environ["REQUEST_METHOD"] = "POST"
    environ["PATH_INFO"] = path
    environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    environ["CONTENT_LENGTH"] = str(len(body))
    environ["wsgi.input"] = BytesIO(body)
    environ["HTTP_USER_AGENT"] = "pytest/pydantic"
    environ["REMOTE_ADDR"] = "127.0.0.1"
    return environ


def _get_environ(path: str = "/") -> dict:
    environ = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = path
    environ["HTTP_USER_AGENT"] = "pytest/pydantic"
    environ["REMOTE_ADDR"] = "127.0.0.1"
    return environ


# ---------------------------------------------------------------------------
# Simple Pydantic models for testing
# ---------------------------------------------------------------------------


class _CommentForm(RequestModel):
    name: str
    comment: str


class _MultiForm(RequestModel):
    first: str
    second: str
    third: str


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pydantic_valid_post_sets_validated_data():
    """Valid POST data is parsed into validated_data on the request."""
    captured = {}

    app, _, _ = setup(middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"])

    @app.route("/submit", allowed_methods=["POST"])
    def submit(request: _CommentForm):
        captured["validated"] = request.validated_data
        return HttpResponse("ok")

    sr = StartResponse()
    result = app(
        _post_environ({"name": "Alice", "comment": "hello"}, path="/submit"), sr
    )

    assert sr.status.startswith("200")
    assert b"ok" in b"".join(result)
    assert captured["validated"].name == "Alice"
    assert captured["validated"].comment == "hello"


def test_pydantic_missing_field_returns_400():
    """POST data missing a required field returns a 400 JSON error."""
    app, _, _ = setup(middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"])

    @app.route("/submit", allowed_methods=["POST"])
    def submit(request: _CommentForm):
        return HttpResponse("should not reach here")  # pragma: no cover

    sr = StartResponse()
    # "comment" is required but not provided
    result = app(_post_environ({"name": "Alice"}, path="/submit"), sr)

    assert sr.status.startswith("400")
    body = json.loads(b"".join(result).decode())
    assert body["message"] == "Validation error"
    assert any("comment" in e for e in body["errors"])


def test_pydantic_get_request_skipped():
    """GET requests are not validated — handler is called directly."""
    captured = {}
    app, _, _ = setup(middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"])

    @app.route("/page")
    def page(request: _CommentForm):
        captured["validated_data"] = request.validated_data
        return HttpResponse("got it")

    sr = StartResponse()
    result = app(_get_environ(path="/page"), sr)

    assert sr.status.startswith("200")
    assert b"got it" in b"".join(result)
    assert captured["validated_data"] == {}


def test_pydantic_unannotated_handler_skipped():
    """A handler without a RequestModel type hint is not validated."""
    app, _, _ = setup(middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"])

    @app.route("/plain", allowed_methods=["POST"])
    def plain(request):
        return HttpResponse("plain ok")

    sr = StartResponse()
    result = app(_post_environ({"anything": "goes"}, path="/plain"), sr)

    assert sr.status.startswith("200")
    assert b"plain ok" in b"".join(result)


def test_pydantic_server_check_passes_when_installed():
    """CheckPydanticInstalled.check() returns None when pydantic is available."""
    from spiderweb.middleware.pydantic import CheckPydanticInstalled

    check = CheckPydanticInstalled(server=None)
    assert check.check() is None


def test_pydantic_server_check_fails_when_not_installed(monkeypatch):
    """CheckPydanticInstalled.check() returns RuntimeError when pydantic is absent."""
    import builtins
    from spiderweb.middleware.pydantic import CheckPydanticInstalled

    real_import = builtins.__import__
    blocked = {"pydantic"}

    def _fake_import(name, *args, **kwargs):
        if name in blocked:
            raise ImportError(f"mocked: {name} not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    check = CheckPydanticInstalled(server=None)
    result = check.check()
    assert isinstance(result, RuntimeError)


def test_pydantic_multiple_errors_reported():
    """All field errors are included in the 400 response."""
    app, _, _ = setup(middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"])

    @app.route("/multi", allowed_methods=["POST"])
    def multi(request: _MultiForm):
        return HttpResponse("ok")  # pragma: no cover

    sr = StartResponse()
    # All three fields missing
    result = app(_post_environ({}, path="/multi"), sr)

    assert sr.status.startswith("400")
    body = json.loads(b"".join(result).decode())
    assert len(body["errors"]) >= 3
