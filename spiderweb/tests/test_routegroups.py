"""Tests for RouteGroup and custom path-parameter converters."""

import pytest

from spiderweb import RouteGroup
from spiderweb.exceptions import ConfigError, ParseError, ReverseNotFound
from spiderweb.response import HttpResponse
from spiderweb.tests.helpers import setup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(**kwargs):
    """Return a bare SpiderwebRouter (no route group)."""
    app, environ, start_response = setup(**kwargs)
    return app, environ, start_response


def call(app, environ, start_response, path, method="GET"):
    environ["PATH_INFO"] = path
    environ["REQUEST_METHOD"] = method
    return app(environ, start_response)


# ---------------------------------------------------------------------------
# RouteGroup — basic prefix routing
# ---------------------------------------------------------------------------


class TestRouteGroupPrefix:
    def test_route_accessible_at_prefixed_path(self):
        rg = RouteGroup(prefix="/api")

        @rg.route("/users")
        def list_users(request):
            return HttpResponse("users")

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        result = call(app, environ, start_response, "/api/users")
        assert result == [b"users"]

    def test_prefix_without_leading_slash_still_works(self):
        """RouteGroup prefix without trailing slash + route with leading slash."""
        rg = RouteGroup(prefix="/v1")

        @rg.route("/items")
        def items(request):
            return HttpResponse("items")

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        result = call(app, environ, start_response, "/v1/items")
        assert result == [b"items"]

    def test_empty_prefix(self):
        rg = RouteGroup()  # no prefix

        @rg.route("/ping")
        def ping(request):
            return HttpResponse("pong")

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        result = call(app, environ, start_response, "/ping")
        assert result == [b"pong"]

    def test_url_params_forwarded_through_routegroup(self):
        rg = RouteGroup(prefix="/api")

        @rg.route("/users/<int:user_id>")
        def user_detail(request, user_id):
            return HttpResponse(str(user_id))

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        result = call(app, environ, start_response, "/api/users/42")
        assert result == [b"42"]

    def test_multiple_routes_in_one_routegroup(self):
        rg = RouteGroup(prefix="/api")

        @rg.route("/a")
        def view_a(request):
            return HttpResponse("a")

        @rg.route("/b")
        def view_b(request):
            return HttpResponse("b")

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        assert call(app, environ, start_response, "/api/a") == [b"a"]
        assert call(app, environ, start_response, "/api/b") == [b"b"]

    def test_two_routegroups_included_independently(self):
        rg1 = RouteGroup(prefix="/v1")
        rg2 = RouteGroup(prefix="/v2")

        @rg1.route("/hello")
        def hello_v1(request):
            return HttpResponse("v1")

        @rg2.route("/hello")
        def hello_v2(request):
            return HttpResponse("v2")

        app, environ, start_response = make_app()
        app.include_routegroup(rg1)
        app.include_routegroup(rg2)

        assert call(app, environ, start_response, "/v1/hello") == [b"v1"]
        assert call(app, environ, start_response, "/v2/hello") == [b"v2"]

    def test_routegroup_add_route_method(self):
        """RouteGroup.add_route() is the non-decorator form."""
        rg = RouteGroup(prefix="/api")

        def handler(request):
            return HttpResponse("direct")

        rg.add_route("/direct", handler, name="direct")

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        result = call(app, environ, start_response, "/api/direct")
        assert result == [b"direct"]

    def test_duplicate_route_via_routegroup_raises(self):
        rg = RouteGroup(prefix="/api")

        @rg.route("/dup")
        def dup(request):
            return HttpResponse("dup")

        app, environ, start_response = make_app()

        @app.route("/api/dup")
        def existing(request):
            return HttpResponse("existing")

        with pytest.raises(ConfigError):
            app.include_routegroup(rg)


# ---------------------------------------------------------------------------
# RouteGroup — namespace / route name namespacing
# ---------------------------------------------------------------------------


class TestRouteGroupNamespace:
    def test_namespaced_reverse(self):
        rg = RouteGroup(prefix="/api", namespace="api")

        @rg.route("/users", name="list")
        def list_users(request):
            return HttpResponse("users")

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        assert app.reverse("api:list") == "/api/users"

    def test_namespaced_reverse_with_url_param(self):
        rg = RouteGroup(prefix="/api", namespace="api")

        @rg.route("/users/<int:id>", name="detail")
        def user_detail(request, id):
            return HttpResponse(str(id))

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        assert app.reverse("api:detail", {"id": 7}) == "/api/users/7"

    def test_no_namespace_keeps_original_name(self):
        rg = RouteGroup(prefix="/api")  # no namespace

        @rg.route("/status", name="status")
        def status(request):
            return HttpResponse("ok")

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        assert app.reverse("status") == "/api/status"

    def test_namespaced_route_not_found_without_namespace(self):
        rg = RouteGroup(prefix="/api", namespace="api")

        @rg.route("/data", name="data")
        def data(request):
            return HttpResponse("data")

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        with pytest.raises(ReverseNotFound):
            app.reverse("data")  # must use "api:data"

    def test_unnamed_route_in_routegroup_has_no_name(self):
        """A route without a name should still work; reverse raises ReverseNotFound."""
        rg = RouteGroup(prefix="/api", namespace="api")

        @rg.route("/anon")
        def anon(request):
            return HttpResponse("anon")

        app, environ, start_response = make_app()
        app.include_routegroup(rg)

        result = call(app, environ, start_response, "/api/anon")
        assert result == [b"anon"]

        with pytest.raises(ReverseNotFound):
            app.reverse("api:anon")  # no name registered

    def test_multiple_namespaced_routegroups(self):
        rg1 = RouteGroup(prefix="/v1", namespace="v1")
        rg2 = RouteGroup(prefix="/v2", namespace="v2")

        @rg1.route("/ping", name="ping")
        def ping_v1(request):
            return HttpResponse("v1")

        @rg2.route("/ping", name="ping")
        def ping_v2(request):
            return HttpResponse("v2")

        app, environ, start_response = make_app()
        app.include_routegroup(rg1)
        app.include_routegroup(rg2)

        assert app.reverse("v1:ping") == "/v1/ping"
        assert app.reverse("v2:ping") == "/v2/ping"


# ---------------------------------------------------------------------------
# Custom path-parameter converters
# ---------------------------------------------------------------------------


class SlugConverter:
    regex = r"[-a-z0-9_]+"
    name = "slug"

    def to_python(self, value):
        return str(value)


class UUIDConverter:
    regex = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    name = "uuid"

    def to_python(self, value):
        return str(value)


class TestCustomConverters:
    def test_register_and_use_custom_converter(self):
        app, environ, start_response = make_app()
        app.register_converter(SlugConverter)

        @app.route("/posts/<slug:slug>")
        def get_post(request, slug):
            return HttpResponse(slug)

        result = call(app, environ, start_response, "/posts/hello-world")
        assert result == [b"hello-world"]

    def test_custom_converter_non_matching_returns_404(self):
        app, environ, start_response = make_app()
        app.register_converter(SlugConverter)

        @app.route("/posts/<slug:slug>")
        def get_post(request, slug):
            return HttpResponse(slug)

        # uppercase not allowed by slug regex
        call(app, environ, start_response, "/posts/Hello-World")
        assert start_response.status.startswith("404")

    def test_to_python_is_called(self):
        """Verify the converter's to_python() transforms the matched value."""

        class UpperConverter:
            regex = r"[a-z]+"
            name = "upper"

            def to_python(self, value):
                return value.upper()

        app, environ, start_response = make_app()
        app.register_converter(UpperConverter)

        @app.route("/shout/<upper:word>")
        def shout(request, word):
            return HttpResponse(word)

        result = call(app, environ, start_response, "/shout/hello")
        assert result == [b"HELLO"]

    def test_two_custom_converters_coexist(self):
        app, environ, start_response = make_app()
        app.register_converter(SlugConverter)
        app.register_converter(UUIDConverter)

        @app.route("/articles/<slug:slug>")
        def by_slug(request, slug):
            return HttpResponse(f"slug:{slug}")

        @app.route("/records/<uuid:uid>")
        def by_uuid(request, uid):
            return HttpResponse(f"uuid:{uid}")

        result = call(app, environ, start_response, "/articles/my-post")
        assert result == [b"slug:my-post"]

        result = call(
            app,
            environ,
            start_response,
            "/records/550e8400-e29b-41d4-a716-446655440000",
        )
        assert result == [b"uuid:550e8400-e29b-41d4-a716-446655440000"]

    def test_custom_converter_unknown_still_raises_parse_error(self):
        app, environ, start_response = make_app()

        with pytest.raises(ParseError):

            @app.route("/x/<badtype:val>")
            def view(request, val):
                return HttpResponse(val)

    def test_custom_converter_name_attribute_used_as_key(self):
        """When the class has a ``name`` attribute, that's what's used in paths."""

        class FooConverter:
            regex = r"foo\d+"
            name = "foo"

            def to_python(self, value):
                return value

        app, environ, start_response = make_app()
        app.register_converter(FooConverter)

        @app.route("/bar/<foo:f>")
        def bar(request, f):
            return HttpResponse(f)

        result = call(app, environ, start_response, "/bar/foo42")
        assert result == [b"foo42"]

    def test_custom_converter_with_routegroup(self):
        """Custom converter registered on the app works inside a RouteGroup."""
        app, environ, start_response = make_app()
        app.register_converter(SlugConverter)

        rg = RouteGroup(prefix="/blog", namespace="blog")

        @rg.route("/<slug:post_slug>", name="post")
        def blog_post(request, post_slug):
            return HttpResponse(post_slug)

        app.include_routegroup(rg)

        result = call(app, environ, start_response, "/blog/cool-article")
        assert result == [b"cool-article"]
        assert (
            app.reverse("blog:post", {"post_slug": "cool-article"})
            == "/blog/cool-article"
        )

    def test_built_in_converters_still_work_after_register(self):
        """Registering custom converters must not break built-in ones."""
        app, environ, start_response = make_app()
        app.register_converter(SlugConverter)

        @app.route("/num/<int:n>")
        def num_view(request, n):
            return HttpResponse(str(n * 2))

        result = call(app, environ, start_response, "/num/21")
        assert result == [b"42"]
