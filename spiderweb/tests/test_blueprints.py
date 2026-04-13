"""Tests for Blueprint (route groups) and custom path-parameter converters."""
import pytest

from spiderweb import Blueprint, SpiderwebRouter
from spiderweb.exceptions import ConfigError, ParseError, ReverseNotFound
from spiderweb.response import HttpResponse, JsonResponse
from spiderweb.tests.helpers import setup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(**kwargs):
    """Return a bare SpiderwebRouter (no blueprint)."""
    app, environ, start_response = setup(**kwargs)
    return app, environ, start_response


def call(app, environ, start_response, path, method="GET"):
    environ["PATH_INFO"] = path
    environ["REQUEST_METHOD"] = method
    return app(environ, start_response)


# ---------------------------------------------------------------------------
# Blueprint — basic prefix routing
# ---------------------------------------------------------------------------


class TestBlueprintPrefix:
    def test_route_accessible_at_prefixed_path(self):
        bp = Blueprint(prefix="/api")

        @bp.route("/users")
        def list_users(request):
            return HttpResponse("users")

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        result = call(app, environ, start_response, "/api/users")
        assert result == [b"users"]

    def test_prefix_without_leading_slash_still_works(self):
        """Blueprint prefix without trailing slash + route with leading slash."""
        bp = Blueprint(prefix="/v1")

        @bp.route("/items")
        def items(request):
            return HttpResponse("items")

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        result = call(app, environ, start_response, "/v1/items")
        assert result == [b"items"]

    def test_empty_prefix(self):
        bp = Blueprint()  # no prefix

        @bp.route("/ping")
        def ping(request):
            return HttpResponse("pong")

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        result = call(app, environ, start_response, "/ping")
        assert result == [b"pong"]

    def test_url_params_forwarded_through_blueprint(self):
        bp = Blueprint(prefix="/api")

        @bp.route("/users/<int:user_id>")
        def user_detail(request, user_id):
            return HttpResponse(str(user_id))

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        result = call(app, environ, start_response, "/api/users/42")
        assert result == [b"42"]

    def test_multiple_routes_in_one_blueprint(self):
        bp = Blueprint(prefix="/api")

        @bp.route("/a")
        def view_a(request):
            return HttpResponse("a")

        @bp.route("/b")
        def view_b(request):
            return HttpResponse("b")

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        assert call(app, environ, start_response, "/api/a") == [b"a"]
        assert call(app, environ, start_response, "/api/b") == [b"b"]

    def test_two_blueprints_included_independently(self):
        bp1 = Blueprint(prefix="/v1")
        bp2 = Blueprint(prefix="/v2")

        @bp1.route("/hello")
        def hello_v1(request):
            return HttpResponse("v1")

        @bp2.route("/hello")
        def hello_v2(request):
            return HttpResponse("v2")

        app, environ, start_response = make_app()
        app.include_blueprint(bp1)
        app.include_blueprint(bp2)

        assert call(app, environ, start_response, "/v1/hello") == [b"v1"]
        assert call(app, environ, start_response, "/v2/hello") == [b"v2"]

    def test_blueprint_add_route_method(self):
        """Blueprint.add_route() is the non-decorator form."""
        bp = Blueprint(prefix="/api")

        def handler(request):
            return HttpResponse("direct")

        bp.add_route("/direct", handler, name="direct")

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        result = call(app, environ, start_response, "/api/direct")
        assert result == [b"direct"]

    def test_duplicate_route_via_blueprint_raises(self):
        bp = Blueprint(prefix="/api")

        @bp.route("/dup")
        def dup(request):
            return HttpResponse("dup")

        app, environ, start_response = make_app()

        @app.route("/api/dup")
        def existing(request):
            return HttpResponse("existing")

        with pytest.raises(ConfigError):
            app.include_blueprint(bp)


# ---------------------------------------------------------------------------
# Blueprint — namespace / route name namespacing
# ---------------------------------------------------------------------------


class TestBlueprintNamespace:
    def test_namespaced_reverse(self):
        bp = Blueprint(prefix="/api", namespace="api")

        @bp.route("/users", name="list")
        def list_users(request):
            return HttpResponse("users")

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        assert app.reverse("api:list") == "/api/users"

    def test_namespaced_reverse_with_url_param(self):
        bp = Blueprint(prefix="/api", namespace="api")

        @bp.route("/users/<int:id>", name="detail")
        def user_detail(request, id):
            return HttpResponse(str(id))

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        assert app.reverse("api:detail", {"id": 7}) == "/api/users/7"

    def test_no_namespace_keeps_original_name(self):
        bp = Blueprint(prefix="/api")  # no namespace

        @bp.route("/status", name="status")
        def status(request):
            return HttpResponse("ok")

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        assert app.reverse("status") == "/api/status"

    def test_namespaced_route_not_found_without_namespace(self):
        bp = Blueprint(prefix="/api", namespace="api")

        @bp.route("/data", name="data")
        def data(request):
            return HttpResponse("data")

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        with pytest.raises(ReverseNotFound):
            app.reverse("data")  # must use "api:data"

    def test_unnamed_route_in_blueprint_has_no_name(self):
        """A route without a name should still work; reverse raises ReverseNotFound."""
        bp = Blueprint(prefix="/api", namespace="api")

        @bp.route("/anon")
        def anon(request):
            return HttpResponse("anon")

        app, environ, start_response = make_app()
        app.include_blueprint(bp)

        result = call(app, environ, start_response, "/api/anon")
        assert result == [b"anon"]

        with pytest.raises(ReverseNotFound):
            app.reverse("api:anon")  # no name registered

    def test_multiple_namespaced_blueprints(self):
        bp1 = Blueprint(prefix="/v1", namespace="v1")
        bp2 = Blueprint(prefix="/v2", namespace="v2")

        @bp1.route("/ping", name="ping")
        def ping_v1(request):
            return HttpResponse("v1")

        @bp2.route("/ping", name="ping")
        def ping_v2(request):
            return HttpResponse("v2")

        app, environ, start_response = make_app()
        app.include_blueprint(bp1)
        app.include_blueprint(bp2)

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
        result = call(app, environ, start_response, "/posts/Hello-World")
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

    def test_custom_converter_with_blueprint(self):
        """Custom converter registered on the app works inside a Blueprint."""
        app, environ, start_response = make_app()
        app.register_converter(SlugConverter)

        bp = Blueprint(prefix="/blog", namespace="blog")

        @bp.route("/<slug:post_slug>", name="post")
        def blog_post(request, post_slug):
            return HttpResponse(post_slug)

        app.include_blueprint(bp)

        result = call(app, environ, start_response, "/blog/cool-article")
        assert result == [b"cool-article"]
        assert app.reverse("blog:post", {"post_slug": "cool-article"}) == "/blog/cool-article"

    def test_built_in_converters_still_work_after_register(self):
        """Registering custom converters must not break built-in ones."""
        app, environ, start_response = make_app()
        app.register_converter(SlugConverter)

        @app.route("/num/<int:n>")
        def num_view(request, n):
            return HttpResponse(str(n * 2))

        result = call(app, environ, start_response, "/num/21")
        assert result == [b"42"]
