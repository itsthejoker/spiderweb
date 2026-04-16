import pytest

from spiderweb.exceptions import MethodNotAllowed
from spiderweb.response import HttpResponse
from spiderweb.routes import View
from spiderweb.tests.helpers import setup


def test_view_init() -> None:
    view = View()
    assert view.template_name is None


def test_view_default_methods_raise_not_allowed() -> None:
    view = View()

    class MockRequest:
        method = "GET"

    request = MockRequest()

    with pytest.raises(MethodNotAllowed):
        view.get(request)
    with pytest.raises(MethodNotAllowed):
        view.post(request)
    with pytest.raises(MethodNotAllowed):
        view.put(request)
    with pytest.raises(MethodNotAllowed):
        view.patch(request)
    with pytest.raises(MethodNotAllowed):
        view.delete(request)
    with pytest.raises(MethodNotAllowed):
        view.head(request)


def test_view_call_dispatch() -> None:
    class MyView(View):
        def get(self, request, *args, **kwargs):
            return HttpResponse("GET response")

        def post(self, request, *args, **kwargs):
            return HttpResponse("POST response")

    view = MyView()

    class MockRequest:
        def __init__(self, method):
            self.method = method

    response_get = view(MockRequest("GET"))
    assert response_get.body == "GET response"

    response_post = view(MockRequest("POST"))
    assert response_post.body == "POST response"


def test_view_call_invalid_method() -> None:
    view = View()

    class MockRequest:
        method = "INVALID"

    with pytest.raises(MethodNotAllowed):
        view(MockRequest())


def test_view_options() -> None:
    class MyView(View):
        def get(self, request):
            pass

        def post(self, request):
            pass

        def some_other_method(self):
            pass

    view = MyView()

    response = view.options(None)
    assert response.status_code == 204

    allow_header = response.headers.get("ALLOW", "")
    allowed_methods = set(allow_header.split(", "))

    assert allowed_methods == {"OPTIONS", "GET", "POST"}


def test_view_options_mro() -> None:
    class BaseView(View):
        def get(self, request):
            pass

    class MiddleView(BaseView):
        def post(self, request):
            pass

    class MyView(MiddleView):
        def patch(self, request):
            pass

    view = MyView()

    response = view.options(None)
    allow_header = response.headers.get("ALLOW", "")
    allowed_methods = set(allow_header.split(", "))

    assert allowed_methods == {"OPTIONS", "GET", "POST", "PATCH"}


def test_functions_with_underscore_are_ignored() -> None:
    class MyView(View):
        def _private_method(self):
            pass

        def __dunder_method__(self):
            pass

    view = MyView()

    response = view.options(None)
    assert response.status_code == 204

    allow_header = response.headers.get("ALLOW", "")
    allowed_methods = set(allow_header.split(", "))

    assert allowed_methods == {"OPTIONS"}


def test_class_based_view_app_route() -> None:
    app, environ, start_response = setup()

    @app.route("/")
    class MyView(View):
        def get(self, request, *args, **kwargs):
            return HttpResponse("GET from app_route")

    environ["PATH_INFO"] = "/"
    environ["REQUEST_METHOD"] = "GET"
    body_iter = app(environ, start_response)
    assert start_response.status.startswith("200")
    assert b"".join(body_iter) == b"GET from app_route"


def test_class_based_view_add_route() -> None:
    app, environ, start_response = setup()

    class MyView(View):
        def get(self, request, *args, **kwargs):
            return HttpResponse("GET from add_route")

    app.add_route("/", MyView)

    environ["PATH_INFO"] = "/"
    environ["REQUEST_METHOD"] = "GET"
    body_iter = app(environ, start_response)
    assert start_response.status.startswith("200")
    assert b"".join(body_iter) == b"GET from add_route"


def test_class_based_view_routes_list() -> None:
    class MyView(View):
        def get(self, request, *args, **kwargs):
            return HttpResponse("GET from routes list")

    app, environ, start_response = setup(routes=[("/", MyView)])

    environ["PATH_INFO"] = "/"
    environ["REQUEST_METHOD"] = "GET"
    body_iter = app(environ, start_response)
    assert start_response.status.startswith("200")
    assert b"".join(body_iter) == b"GET from routes list"
