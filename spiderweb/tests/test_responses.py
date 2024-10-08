import pytest

from spiderweb import ConfigError
from spiderweb.constants import DEFAULT_ENCODING
from spiderweb.exceptions import (
    NoResponseError,
    SpiderwebNetworkException,
    SpiderwebException,
    ReverseNotFound,
    GeneralException,
)
from spiderweb.response import (
    HttpResponse,
    JsonResponse,
    TemplateResponse,
    RedirectResponse,
    FileResponse,
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
    def index(request):
        return RedirectResponse(location="/redirected")

    def view2(request):
        return HttpResponse("View 2")

    app, environ, start_response = setup(
        routes=[
            ("/", index, {"allowed_methods": ["GET", "POST"], "csrf_exempt": True}),
            ("/view2", view2),
        ]
    )

    assert app(environ, start_response) == [b"None"]
    assert start_response.get_headers()["location"] == "/redirected"


def test_redirect_on_append_slash():
    app, environ, start_response = setup(append_slash=True)

    @app.route("/hello")
    def index(request):
        pass

    environ["PATH_INFO"] = "/hello"
    assert app(environ, start_response) == [b"None"]
    assert start_response.get_headers()["location"] == "/hello/"


@given(st.text())
def test_template_response_with_template(text):
    app, environ, start_response = setup(templates_dirs=["spiderweb/tests"])

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

    def custom_404(request):
        return HttpResponse("Custom 404 2")

    app, environ, start_response = setup(error_routes={404: custom_404})

    assert app(environ, start_response) == [b"Custom 404 2"]


def test_getting_nonexistent_error_view():
    app, environ, start_response = setup()

    assert app.get_error_route(10101).__name__ == "http500"


def test_view_gets_name():
    app, environ, start_response = setup()

    @app.route("/", name="asdfasdf")
    def index(request): ...

    assert [v for k, v in app._routes.items()][0]["name"] == "asdfasdf"


def test_view_can_be_reversed():
    app, environ, start_response = setup()

    @app.route("/", name="asdfasdf")
    def index(request): ...

    @app.route("/<int:hi>", name="qwer")
    def index2(request, hi): ...

    assert app.reverse("asdfasdf") == "/"
    assert app.reverse("asdfasdf", {"id": 1}) == "/"
    assert app.reverse("asdfasdf", {"id": 1}, query={"key": "value"}) == "/?key=value"

    assert app.reverse("qwer", {"hi": 1}) == "/1"
    assert app.reverse("qwer", {"hi": 1}, query={"key": "value"}) == "/1?key=value"


def test_reversed_views_explode_when_missing_all_args():
    app, environ, start_response = setup()

    @app.route("/<int:hi>", name="qwer")
    def index(request, hi): ...

    with pytest.raises(SpiderwebException):
        app.reverse("qwer")


def test_reversed_views_explode_when_missing_some_args():
    app, environ, start_response = setup()

    @app.route("/<int:hi>/<str:bye>", name="qwer")
    def index(request, hi, bye): ...

    with pytest.raises(SpiderwebException):
        app.reverse("qwer", {"hi": 1})


def test_reverse_nonexistent_view():
    app, environ, start_response = setup()

    with pytest.raises(ReverseNotFound):
        app.reverse("qwer")


def test_setting_content_type_header():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        resp = HttpResponse("Hello, World!", headers={"content-type": "text/html"})
        return resp

    response = app(environ, start_response)
    assert response == [b"Hello, World!"]
    assert start_response.get_headers()["content-type"] == "text/html"


def test_httpresponse_str_returns_body():
    resp = HttpResponse("Hello, World!")
    assert str(resp) == "Hello, World!"


def test_template_response_with_no_templates_raises_errors():
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        return TemplateResponse(request, "")

    with pytest.raises(GeneralException) as exc:
        app(environ, start_response)

    assert (
        str(exc.value) == "GeneralException() - TemplateResponse requires a template."
    )


def test_template_response_with_no_template_dirs():

    template = TemplateResponse("", "test.html")

    with pytest.raises(GeneralException) as exc:
        template.render()

    assert str(exc.value) == (
        "GeneralException() - TemplateResponse has no loader. Did you set templates_dirs?"
    )


def test_file_response():
    resp = FileResponse("spiderweb/tests/staticfiles/file_for_testing_fileresponse.txt")
    assert resp.headers["content-type"] == "text/plain"
    assert resp.render() == [b"hi"]


def test_requesting_static_file():
    app, environ, start_response = setup(
        staticfiles_dirs=["spiderweb/tests/staticfiles"], debug=True
    )

    environ["PATH_INFO"] = "/static/file_for_testing_fileresponse.txt"

    assert app(environ, start_response) == [b"hi"]


def test_requesting_nonexistent_static_file():
    app, environ, start_response = setup(
        staticfiles_dirs=["spiderweb/tests/staticfiles"], debug=True
    )

    environ["PATH_INFO"] = "/static/does_not_exist.txt"

    assert app(environ, start_response) == [
        b"Something went wrong.\n\n"
        b"Code: 404\n\n"
        b"Msg: Not Found\n\n"
        b"Desc: The requested resource could not be found"
    ]


def test_static_file_with_unsafe_path():
    app, environ, start_response = setup(
        staticfiles_dirs=["spiderweb/tests/staticfiles"], debug=True
    )

    environ["PATH_INFO"] = "/static/../__init__.py"

    assert app(environ, start_response) == [
        b"Something went wrong.\n\n"
        b"Code: 404\n\n"
        b"Msg: Not Found\n\n"
        b"Desc: The requested resource could not be found"
    ]
