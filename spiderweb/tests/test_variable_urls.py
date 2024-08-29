import pytest

from spiderweb import SpiderwebRouter
from spiderweb.constants import DEFAULT_ENCODING
from spiderweb.exceptions import ParseError, ConfigError
from spiderweb.response import (
    HttpResponse,
    JsonResponse,
    TemplateResponse,
    RedirectResponse,
)
from hypothesis import given, strategies as st, assume

from peewee import SqliteDatabase

from spiderweb.tests.helpers import setup


@given(st.text())
def test_str_converter(text):
    assume(len(text) > 0)
    assume("/" not in text)
    app, environ, start_response = setup()

    @app.route("/<str:test_input>")
    def index(request, test_input: str):
        return HttpResponse(test_input)

    environ["PATH_INFO"] = f"/{text}"
    assert app(environ, start_response) == [bytes(text, DEFAULT_ENCODING)]


@given(st.text())
def test_default_str_converter(text):
    assume(len(text) > 0)
    assume("/" not in text)
    app, environ, start_response = setup()

    @app.route("/<test_input>")
    def index(request, test_input: str):
        return HttpResponse(test_input)

    environ["PATH_INFO"] = f"/{text}"
    assert app(environ, start_response) == [bytes(text, DEFAULT_ENCODING)]


def test_unknown_converter():
    app, environ, start_response = setup()

    with pytest.raises(ParseError):

        @app.route("/<asdf:test_input>")
        def index(request, test_input: str):
            return HttpResponse(test_input)


def test_duplicate_route():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request): ...

    with pytest.raises(ConfigError):

        @app.route("/")
        def index(request): ...


def test_url_with_double_underscore():
    app, environ, start_response = setup()

    with pytest.raises(ConfigError):

        @app.route("/<asdf:test__input>")
        def index(request, test_input: str):
            return HttpResponse(test_input)


@given(st.integers())
def test_int_converter(integer):
    assume(integer > 0)
    app, environ, start_response = setup()

    @app.route("/<int:test_input>")
    def index(request, test_input: str):
        return HttpResponse(test_input)

    environ["PATH_INFO"] = f"/{integer}"
    assert app(environ, start_response) == [bytes(str(integer), DEFAULT_ENCODING)]


@pytest.mark.parametrize(
    "number",
    [
        1.0000000000000002,
        294744.2324,
        0000.3,
    ],
)
def test_float_converter(number):
    app, environ, start_response = setup()

    @app.route("/<float:test_input>")
    def index(request, test_input: str):
        return HttpResponse(test_input)

    environ["PATH_INFO"] = f"/{number}"
    assert app(environ, start_response) == [bytes(str(number), DEFAULT_ENCODING)]
