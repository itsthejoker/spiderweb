import pytest

from spiderweb import SpiderwebRouter, ConfigError
from spiderweb.constants import DEFAULT_ENCODING
from spiderweb.exceptions import NoResponseError, SpiderwebNetworkException
from spiderweb.response import (
    HttpResponse,
    JsonResponse,
    TemplateResponse,
    RedirectResponse,
)
from hypothesis import given, strategies as st

from spiderweb.tests.helpers import setup


@given(st.text())
def test_http_response(text):
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        return HttpResponse(text)

    assert app(environ, start_response) == [bytes(text, DEFAULT_ENCODING)]


def test_json_response():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        return JsonResponse(data={"message": "text"})

    assert app(environ, start_response) == [
        bytes('{"message": "text"}', DEFAULT_ENCODING)
    ]


def test_dict_response():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        return {"message": "Hello, World!"}

    assert app(environ, start_response) == [b'{"message": "Hello, World!"}']


@given(st.text())
def test_template_response(text):
    app, environ, start_response = setup()
    template = "MESSAGE: {{ message }}"

    @app.route("/")
    def index(request):
        return TemplateResponse(
            request, template_string=template, context={"message": text}
        )

    assert app(environ, start_response) == [
        b"MESSAGE: " + bytes(text, DEFAULT_ENCODING)
    ]


def test_redirect_response():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        return RedirectResponse(location="/redirected")

    assert app(environ, start_response) == [b"None"]
    assert start_response.get_headers()["location"] == "/redirected"


def test_add_route_at_server_start():
    app, environ, start_response = setup()

    def index(request):
        return RedirectResponse(location="/redirected")

    def view2(request):
        return HttpResponse("View 2")

    app = SpiderwebRouter(
        routes=[
            ("/", index, {"allowed_methods": ["GET", "POST"], "csrf_exempt": True}),
            ("/view2", view2),
        ]
    )

    assert app(environ, start_response) == [b"None"]
    assert start_response.get_headers()["location"] == "/redirected"


def test_redirect_on_append_slash():
    _, environ, start_response = setup()
    app = SpiderwebRouter(append_slash=True)

    @app.route("/hello")
    def index(request):
        pass

    environ["PATH_INFO"] = f"/hello"
    assert app(environ, start_response) == [b"None"]
    assert start_response.get_headers()["location"] == "/hello/"


@given(st.text())
def test_template_response_with_template(text):
    _, environ, start_response = setup()

    app = SpiderwebRouter(templates_dirs=["spiderweb/tests"])

    @app.route("/")
    def index(request):
        return TemplateResponse(request, "test.html", context={"message": text})

    assert app(environ, start_response) == [
        b"TEMPLATE! " + bytes(text, DEFAULT_ENCODING)
    ]


def test_view_returns_none():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        pass

    with pytest.raises(NoResponseError):
        assert app(environ, start_response) == [b"None"]


def test_exploding_view():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        raise SpiderwebNetworkException("Boom!")

    assert app(environ, start_response) == [
        b"Something went wrong.\n\nCode: Boom!\n\nMsg: None\n\nDesc: None"
    ]


def test_missing_view():
    app, environ, start_response = setup()

    assert app(environ, start_response) == [b'{"error": "Route `/` not found"}']


def test_missing_view_with_custom_404():
    app, environ, start_response = setup()

    @app.error(404)
    def custom_404(request):
        return HttpResponse("Custom 404")

    assert app(environ, start_response) == [b"Custom 404"]


def test_duplicate_error_view():
    app, environ, start_response = setup()

    @app.error(404)
    def custom_404(request): ...

    with pytest.raises(ConfigError):

        @app.error(404)
        def custom_404(request): ...


def test_missing_view_with_custom_404_alt():
    _, environ, start_response = setup()

    def custom_404(request):
        return HttpResponse("Custom 404 2")

    app = SpiderwebRouter(error_routes={404: custom_404})

    assert app(environ, start_response) == [b"Custom 404 2"]
