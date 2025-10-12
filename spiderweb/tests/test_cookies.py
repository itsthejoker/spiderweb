from datetime import datetime
import json as _json

import pytest

from spiderweb import HttpResponse
from spiderweb.exceptions import GeneralException
from spiderweb.tests.helpers import setup


def test_valid_cookie():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        resp = HttpResponse("Hello, World!")
        resp.set_cookie("cookie", "value")
        return resp

    response = app(environ, start_response)
    assert response == [b"Hello, World!"]
    assert start_response.get_headers()["set-cookie"] == "cookie=value"


def test_invalid_cookie_name():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        resp = HttpResponse("Hello, World!")
        resp.set_cookie("cookie$%^&*name", "value")
        return resp

    with pytest.raises(GeneralException) as exc:
        app(environ, start_response)

    assert str(exc.value) == (
        "GeneralException() - Cookie name has illegal characters."
        " See https://developer.mozilla.org/en-US/docs/Web/HTTP/"
        "Headers/Set-Cookie#attributes for information on allowed"
        " characters."
    )


def test_cookie_with_domain():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        resp = HttpResponse("Hello, World!")
        resp.set_cookie("cookie", "value", domain="example.com")
        return resp

    response = app(environ, start_response)
    assert response == [b"Hello, World!"]
    assert (
        start_response.get_headers()["set-cookie"] == "cookie=value; Domain=example.com"
    )


def test_cookie_with_expires():
    app, environ, start_response = setup()
    expiry_time = datetime(2024, 10, 22, 7, 28)
    expiry_time_str = expiry_time.strftime("%a, %d %b %Y %H:%M:%S GMT")

    @app.route("/")
    def index(request):
        resp = HttpResponse("Hello, World!")
        resp.set_cookie("cookie", "value", expires=expiry_time)
        return resp

    response = app(environ, start_response)
    assert response == [b"Hello, World!"]
    assert (
        start_response.get_headers()["set-cookie"]
        == f"cookie=value; Expires={expiry_time_str}"
    )


def test_cookie_with_max_age():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        resp = HttpResponse("Hello, World!")
        resp.set_cookie("cookie", "value", max_age=3600)
        return resp

    response = app(environ, start_response)
    assert response == [b"Hello, World!"]
    assert start_response.get_headers()["set-cookie"] == "cookie=value; Max-Age=3600"


def test_cookie_with_invalid_samesite_attr():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        resp = HttpResponse("Hello, World!")
        resp.set_cookie("cookie", "value", same_site="invalid")
        return resp

    with pytest.raises(GeneralException) as exc:
        app(environ, start_response)

    assert str(exc.value) == (
        "GeneralException() - Invalid value invalid for `same_site` cookie"
        " attribute. Valid options are 'strict', 'lax', or 'none'."
    )


def test_cookie_partitioned_attr():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        resp = HttpResponse()
        resp.set_cookie("cookie", "value", partitioned=True)
        return resp

    app(environ, start_response)
    assert start_response.get_headers()["set-cookie"] == "cookie=value; Partitioned"


def test_cookie_secure_attr():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        resp = HttpResponse()
        resp.set_cookie("cookie", "value", secure=True)
        return resp

    app(environ, start_response)
    assert start_response.get_headers()["set-cookie"] == "cookie=value; Secure"


def test_setting_multiple_cookies():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        resp = HttpResponse()
        resp.set_cookie("cookie1", "value1")
        resp.set_cookie("cookie2", "value2")
        return resp

    app(environ, start_response)
    assert start_response.headers[-1] == ("set-cookie", "cookie2=value2")
    assert start_response.headers[-2] == ("set-cookie", "cookie1=value1")


@pytest.mark.parametrize(
    "cookie_header,expected",
    [
        ("", {}),
        (" ", {}),
        (";", {}),
        (";; ; ", {}),
        ("a=1", {"a": "1"}),
        ("a=1; b=2", {"a": "1", "b": "2"}),
        ("a=1; b", {"a": "1"}),  # flag-like segment ignored
        ("flag", {}),  # single flag ignored
        ("a=1; flag; c=3", {"a": "1", "c": "3"}),
        ("a=1; c=", {"a": "1", "c": ""}),  # empty value allowed
        ("token=abc=def==", {"token": "abc=def=="}),  # values may contain '='
        ("   d = q   ", {"d": "q"}),  # tolerate spaces around name/value
        ("a=1; ; ; c=3", {"a": "1", "c": "3"}),  # empty segments ignored
        ("a=1; a=2", {"a": "2"}),  # last duplicate wins
        ('q="a b c"', {"q": '"a b c"'}),  # quotes preserved
        ("u=hello%3Dworld", {"u": "hello%3Dworld"}),  # url-encoded preserved
        (
            "=novalue; a=1",
            {"": "novalue", "a": "1"},
        ),  # empty name retained per current parser
        ("lead=1; ; trail=2;", {"lead": "1", "trail": "2"}),
        (" spaced = value ; another= thing ", {"spaced": "value", "another": "thing"}),
        (
            "a=1; b=2; flag; c=; token=abc=def==;   d = q ; ;",
            {"a": "1", "b": "2", "c": "", "token": "abc=def==", "d": "q"},
        ),
    ],
    ids=[
        "empty",
        "space-only",
        "single-semicolon",
        "many-empty",
        "single-pair",
        "two-pairs",
        "flag-after",
        "single-flag",
        "mix-flag",
        "empty-value",
        "value-with-equals",
        "spaces-around",
        "ignore-empty-segments",
        "duplicate-last-wins",
        "quoted-value",
        "url-encoded",
        "empty-name",
        "lead-trail-with-empties",
        "spaces-around-multi",
        "mixed-case-from-original",
    ],
)
def test_cookie_parsing_tolerates_malformed_segments(cookie_header, expected):
    app, environ, start_response = setup()

    from spiderweb.response import JsonResponse

    @app.route("/")
    def index(request):
        return JsonResponse(data=request.COOKIES)

    environ["HTTP_COOKIE"] = cookie_header

    body = app(environ, start_response)[0].decode("utf-8")
    data = _json.loads(body)
    assert data == expected
