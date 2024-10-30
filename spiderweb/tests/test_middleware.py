from io import BytesIO, BufferedReader
from datetime import timedelta

import pytest
from peewee import SqliteDatabase

from spiderweb import SpiderwebRouter, HttpResponse, StartupErrors, ConfigError
from spiderweb.constants import DEFAULT_ENCODING
from spiderweb.middleware.cors import (
    ACCESS_CONTROL_ALLOW_ORIGIN,
    ACCESS_CONTROL_ALLOW_HEADERS,
    ACCESS_CONTROL_ALLOW_METHODS,
    ACCESS_CONTROL_EXPOSE_HEADERS,
    ACCESS_CONTROL_ALLOW_CREDENTIALS,
    ACCESS_CONTROL_MAX_AGE,
    ACCESS_CONTROL_ALLOW_PRIVATE_NETWORK,
)
from spiderweb.middleware.sessions import Session
from spiderweb.middleware import csrf
from spiderweb.tests.helpers import setup
from spiderweb.tests.views_for_tests import (
    form_view_with_csrf,
    form_csrf_exempt,
    form_view_without_csrf,
    text_view,
    unauthorized_view,
    file_view,
)
from spiderweb.middleware.gzip import (
    CheckValidGzipMinimumLength,
    CheckValidGzipCompressionLevel,
)


def index(request):
    if "value" in request.SESSION:
        request.SESSION["value"] += 1
    else:
        request.SESSION["value"] = 0
    return HttpResponse(body=str(request.SESSION["value"]))


def test_session_middleware():
    app, environ, start_response = setup(
        middleware=["spiderweb.middleware.sessions.SessionMiddleware"],
    )

    app.add_route("/", index)

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "1.1.1.1"

    assert app(environ, start_response) == [bytes(str(0), DEFAULT_ENCODING)]

    session_key = Session.select().first().session_key
    environ["HTTP_COOKIE"] = f"swsession={session_key}"

    assert app(environ, start_response) == [bytes(str(1), DEFAULT_ENCODING)]
    assert app(environ, start_response) == [bytes(str(2), DEFAULT_ENCODING)]


def test_expired_session():
    app, environ, start_response = setup(
        middleware=["spiderweb.middleware.sessions.SessionMiddleware"],
    )

    app.add_route("/", index)

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "1.1.1.1"

    assert app(environ, start_response) == [bytes(str(0), DEFAULT_ENCODING)]

    session = Session.select().first()
    session.created_at = session.created_at - timedelta(seconds=app.session_max_age)
    session.save()

    environ["HTTP_COOKIE"] = f"swsession={session.session_key}"

    # it shouldn't increment because we get a new session
    assert app(environ, start_response) == [bytes(str(0), DEFAULT_ENCODING)]

    session2 = list(Session.select())[-1]
    assert session2.session_key != session.session_key


def test_exploding_middleware():
    app, environ, start_response = setup(
        middleware=[
            "spiderweb.tests.middleware.ExplodingRequestMiddleware",
            "spiderweb.tests.middleware.ExplodingResponseMiddleware",
        ],
    )

    app.add_route("/", index)

    assert app(environ, start_response) == [bytes(str(0), DEFAULT_ENCODING)]
    # make sure it kicked out the middleware and isn't just ignoring it
    assert len(app.middleware) == 0


def test_invalid_middleware():
    with pytest.raises(ConfigError) as e:
        SpiderwebRouter(middleware=["nonexistent.middleware"])

    assert e.value.args[0] == "Middleware 'nonexistent.middleware' not found."


def test_csrf_middleware_without_session_middleware():
    with pytest.raises(StartupErrors) as e:
        SpiderwebRouter(
            middleware=["spiderweb.middleware.csrf.CSRFMiddleware"],
            db=SqliteDatabase("spiderweb-tests.db"),
        )
    exceptiongroup = e.value.args[1]
    assert (
        exceptiongroup[0].args[0]
        == csrf.CheckForSessionMiddleware.SESSION_MIDDLEWARE_NOT_FOUND
    )


def test_csrf_middleware_above_session_middleware():
    with pytest.raises(StartupErrors) as e:
        app, environ, start_response = setup(
            middleware=[
                "spiderweb.middleware.csrf.CSRFMiddleware",
                "spiderweb.middleware.sessions.SessionMiddleware",
            ],
        )

    exceptiongroup = e.value.args[1]
    assert (
        exceptiongroup[0].args[0]
        == csrf.VerifyCorrectMiddlewarePlacement.SESSION_MIDDLEWARE_BELOW_CSRF
    )


def test_csrf_middleware():
    app, environ, start_response = setup(
        middleware=[
            "spiderweb.middleware.sessions.SessionMiddleware",
            "spiderweb.middleware.csrf.CSRFMiddleware",
        ],
    )

    app.add_route("/", form_view_with_csrf, ["GET", "POST"])

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "1.1.1.1"

    resp = app(environ, start_response)[0].decode(DEFAULT_ENCODING)

    assert "<form" in resp
    assert '<input type="hidden" name="csrf_token"' in resp

    token = resp.split('value="')[1].split('"')[0]

    formdata = f"name=bob&csrf_token={token}"
    environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    environ["HTTP_COOKIE"] = (
        f"swsession={[i for i in Session.select().dicts()][-1]['session_key']}"
    )
    environ["REQUEST_METHOD"] = "POST"
    environ["HTTP_X_CSRF_TOKEN"] = token
    environ["CONTENT_LENGTH"] = len(formdata)

    # setup form data
    b_handle = BytesIO()
    b_handle.write(formdata.encode(DEFAULT_ENCODING))
    b_handle.seek(0)

    environ["wsgi.input"] = BufferedReader(b_handle)

    resp2 = app(environ, start_response)[0].decode(DEFAULT_ENCODING)

    assert "bob" in resp2

    # test that it raises a CSRF error on wrong token
    formdata = "name=bob&csrf_token=badtoken"
    b_handle = BytesIO()
    b_handle.write(formdata.encode(DEFAULT_ENCODING))
    b_handle.seek(0)
    environ["wsgi.input"] = BufferedReader(b_handle)
    environ["HTTP_X_CSRF_TOKEN"] = None
    resp3 = app(environ, start_response)[0].decode(DEFAULT_ENCODING)
    assert "CSRF token is invalid" in resp3

    # test that the wrong session also raises a CSRF error
    token = app.decrypt(token).split("::")[0]
    token = app.encrypt(f"{token}::badsession").decode(DEFAULT_ENCODING)
    formdata = f"name=bob&csrf_token={token}"
    b_handle = BytesIO()
    b_handle.write(formdata.encode(DEFAULT_ENCODING))
    b_handle.seek(0)

    environ["wsgi.input"] = BufferedReader(b_handle)
    resp4 = app(environ, start_response)[0].decode(DEFAULT_ENCODING)
    assert "CSRF token is invalid" in resp4


def test_csrf_expired_token():
    app, environ, start_response = setup(
        middleware=[
            "spiderweb.middleware.sessions.SessionMiddleware",
            "spiderweb.middleware.csrf.CSRFMiddleware",
        ],
    )

    app.middleware[1].CSRF_EXPIRY = -1

    app.add_route("/", form_view_with_csrf, ["GET", "POST"])

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "1.1.1.1"
    resp = app(environ, start_response)[0].decode(DEFAULT_ENCODING)
    token = resp.split('value="')[1].split('"')[0]

    formdata = f"name=bob&csrf_token={token}"
    environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    environ["HTTP_COOKIE"] = (
        f"swsession={[i for i in Session.select().dicts()][-1]['session_key']}"
    )
    environ["REQUEST_METHOD"] = "POST"
    environ["HTTP_ORIGIN"] = "example.com"
    environ["HTTP_X_CSRF_TOKEN"] = token
    environ["CONTENT_LENGTH"] = len(formdata)

    b_handle = BytesIO()
    b_handle.write(formdata.encode(DEFAULT_ENCODING))
    b_handle.seek(0)

    environ["wsgi.input"] = BufferedReader(b_handle)
    resp = app(environ, start_response)[0].decode(DEFAULT_ENCODING)
    assert "CSRF token is invalid" in resp


def test_csrf_exempt():
    app, environ, start_response = setup(
        middleware=[
            "spiderweb.middleware.sessions.SessionMiddleware",
            "spiderweb.middleware.csrf.CSRFMiddleware",
        ],
    )

    app.add_route("/", form_csrf_exempt, ["GET", "POST"])
    app.add_route("/2", form_view_without_csrf, ["GET", "POST"])

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "1.1.1.1"
    environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    environ["REQUEST_METHOD"] = "POST"

    formdata = "name=bob"
    environ["CONTENT_LENGTH"] = len(formdata)
    b_handle = BytesIO()
    b_handle.write(formdata.encode(DEFAULT_ENCODING))
    b_handle.seek(0)

    environ["wsgi.input"] = BufferedReader(b_handle)
    resp = app(environ, start_response)[0].decode(DEFAULT_ENCODING)
    assert "bob" in resp

    environ["PATH_INFO"] = "/2"
    resp2 = app(environ, start_response)[0].decode(DEFAULT_ENCODING)
    assert "CSRF token is invalid" in resp2


def test_csrf_trusted_origins():
    app, environ, start_response = setup(
        middleware=[
            "spiderweb.middleware.sessions.SessionMiddleware",
            "spiderweb.middleware.csrf.CSRFMiddleware",
        ],
        csrf_trusted_origins=[
            "example.com",
        ],
    )
    app.add_route("/", form_view_without_csrf, ["GET", "POST"])

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "1.1.1.1"
    environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    environ["REQUEST_METHOD"] = "POST"

    formdata = "name=bob"
    environ["CONTENT_LENGTH"] = len(formdata)
    b_handle = BytesIO()
    b_handle.write(formdata.encode(DEFAULT_ENCODING))
    b_handle.seek(0)
    environ["wsgi.input"] = BufferedReader(b_handle)

    environ["HTTP_ORIGIN"] = "notvalid.com"
    resp = app(environ, start_response)[0].decode(DEFAULT_ENCODING)
    assert "CSRF token is invalid" in resp

    b_handle = BytesIO()
    b_handle.write(formdata.encode(DEFAULT_ENCODING))
    b_handle.seek(0)
    environ["wsgi.input"] = BufferedReader(b_handle)

    environ["HTTP_ORIGIN"] = "example.com"
    resp2 = app(environ, start_response)[0].decode(DEFAULT_ENCODING)
    assert resp2 == '{"name": "bob"}'


def test_post_process_middleware():
    app, environ, start_response = setup(
        middleware=[
            "spiderweb.tests.middleware.PostProcessingMiddleware",
        ],
    )

    app.add_route("/", text_view)

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "/"
    environ["REQUEST_METHOD"] = "GET"

    assert app(environ, start_response) == [bytes("Hi! Moo!", DEFAULT_ENCODING)]


def test_post_process_header_manip():
    app, environ, start_response = setup(
        middleware=[
            "spiderweb.tests.middleware.PostProcessingWithHeaderManipulation",
        ],
    )

    app.add_route("/", text_view)

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "/"
    environ["REQUEST_METHOD"] = "GET"

    assert app(environ, start_response) == [bytes("Hi!", DEFAULT_ENCODING)]
    assert start_response.get_headers()["x-moo"] == "true"


def test_unused_post_process_middleware():
    app, environ, start_response = setup(
        middleware=[
            "spiderweb.tests.middleware.ExplodingPostProcessingMiddleware",
        ],
    )

    app.add_route("/", text_view)

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "/"
    environ["REQUEST_METHOD"] = "GET"

    assert app(environ, start_response) == [bytes("Hi!", DEFAULT_ENCODING)]
    # make sure it kicked out the middleware and isn't just ignoring it
    assert len(app.middleware) == 0


class TestGzipMiddleware:
    middleware = {"middleware": ["spiderweb.middleware.gzip.GzipMiddleware"]}

    def test_not_enabled_on_small_response(self):
        app, environ, start_response = setup(
            **self.middleware,
            gzip_minimum_response_length=500,
        )
        app.add_route("/", text_view)

        environ["HTTP_USER_AGENT"] = "hi"
        environ["REMOTE_ADDR"] = "/"
        environ["REQUEST_METHOD"] = "GET"

        assert app(environ, start_response) == [bytes("Hi!", DEFAULT_ENCODING)]
        assert "Content-Encoding" not in start_response.get_headers()

    def test_changing_minimum_response_length(self):
        app, environ, start_response = setup(
            **self.middleware,
            gzip_minimum_response_length=1,
        )
        app.add_route("/", text_view)

        environ["HTTP_ACCEPT_ENCODING"] = "gzip"
        environ["HTTP_USER_AGENT"] = "hi"
        environ["REMOTE_ADDR"] = "/"
        environ["REQUEST_METHOD"] = "GET"
        assert str(app(environ, start_response)[0]).startswith("b'\\x1f\\x8b\\x08")
        assert "content-encoding" in start_response.get_headers()

    def test_not_enabled_on_error_response(self):
        app, environ, start_response = setup(
            **self.middleware,
            gzip_minimum_response_length=1,
        )
        app.add_route("/", unauthorized_view)

        environ["HTTP_ACCEPT_ENCODING"] = "gzip"
        environ["HTTP_USER_AGENT"] = "hi"
        environ["REMOTE_ADDR"] = "/"
        environ["REQUEST_METHOD"] = "GET"
        assert app(environ, start_response) == [bytes("Unauthorized", DEFAULT_ENCODING)]
        assert "content-encoding" not in start_response.get_headers()

    def test_not_enabled_on_bytes_response(self):
        app, environ, start_response = setup(
            **self.middleware,
            gzip_minimum_response_length=1,
        )
        # send a file that's already in bytes form
        app.add_route("/", file_view)

        environ["HTTP_ACCEPT_ENCODING"] = "gzip"
        environ["HTTP_USER_AGENT"] = "hi"
        environ["REMOTE_ADDR"] = "/"
        environ["REQUEST_METHOD"] = "GET"
        assert app(environ, start_response) == [bytes("hi", DEFAULT_ENCODING)]
        assert "content-encoding" not in start_response.get_headers()

    def test_invalid_response_length(self):
        class FakeServer:
            gzip_minimum_response_length = "asdf"

        with pytest.raises(ConfigError) as e:
            CheckValidGzipMinimumLength(server=FakeServer).check()
        assert (
            e.value.args[0] == CheckValidGzipMinimumLength.INVALID_GZIP_MINIMUM_LENGTH
        )

    def test_negative_response_length(self):
        class FakeServer:
            gzip_minimum_response_length = -1

        with pytest.raises(ConfigError) as e:
            CheckValidGzipMinimumLength(server=FakeServer).check()
        assert (
            e.value.args[0] == CheckValidGzipMinimumLength.INVALID_GZIP_MINIMUM_LENGTH
        )

    def test_bad_compression_level(self):
        class FakeServer:
            gzip_compression_level = "asdf"

        with pytest.raises(ConfigError) as e:
            CheckValidGzipCompressionLevel(server=FakeServer).check()
        assert (
            e.value.args[0]
            == CheckValidGzipCompressionLevel.INVALID_GZIP_COMPRESSION_LEVEL
        )


class TestCorsMiddleware:
    # adapted from:
    # https://github.com/adamchainz/django-cors-headers/blob/main/tests/test_middleware.py
    # to make sure I didn't miss anything
    middleware = {"middleware": ["spiderweb.middleware.cors.CorsMiddleware"]}

    def test_get_no_origin(self):
        app, environ, start_response = setup(
            **self.middleware, cors_allow_all_origins=True
        )
        app(environ, start_response)
        assert ACCESS_CONTROL_ALLOW_ORIGIN not in start_response.get_headers()

    def test_get_origin_vary_by_default(self):
        app, environ, start_response = setup(
            **self.middleware, cors_allow_all_origins=True
        )
        app(environ, start_response)
        assert start_response.get_headers()["vary"] == "origin"

    def test_get_invalid_origin(self):
        app, environ, start_response = setup(
            **self.middleware, cors_allow_all_origins=True
        )
        environ["HTTP_ORIGIN"] = "https://example.com]"
        app(environ, start_response)
        assert ACCESS_CONTROL_ALLOW_ORIGIN not in start_response.get_headers()

    def test_get_not_in_allowed_origins(self):
        app, environ, start_response = setup(
            **self.middleware, cors_allowed_origins=["https://example.com"]
        )
        environ["HTTP_ORIGIN"] = "https://example.org"
        app(environ, start_response)
        assert ACCESS_CONTROL_ALLOW_ORIGIN not in start_response.get_headers()

    def test_get_not_in_allowed_origins_due_to_wrong_scheme(self):
        app, environ, start_response = setup(
            **self.middleware, cors_allowed_origins=["http://example.org"]
        )
        environ["HTTP_ORIGIN"] = "https://example.org"
        app(environ, start_response)
        assert ACCESS_CONTROL_ALLOW_ORIGIN not in start_response.get_headers()

    def test_get_in_allowed_origins(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origins=["https://example.com", "https://example.org"],
        )
        environ["HTTP_ORIGIN"] = "https://example.org"
        app(environ, start_response)
        assert (
            start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN]
            == "https://example.org"
        )

    def test_null_in_allowed_origins(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origins=["https://example.com", "null"],
        )
        environ["HTTP_ORIGIN"] = "null"
        app(environ, start_response)
        assert start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN] == "null"

    def test_file_in_allowed_origins(self):
        """
        'file://' should be allowed as an origin since Chrome on Android
        mistakenly sends it
        """
        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origins=["https://example.com", "file://"],
        )
        environ["HTTP_ORIGIN"] = "file://"
        app(environ, start_response)
        assert start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN] == "file://"

    def test_get_expose_headers(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_all_origins=True,
            cors_expose_headers=["accept", "content-type"],
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        app(environ, start_response)
        assert (
            start_response.get_headers()[ACCESS_CONTROL_EXPOSE_HEADERS]
            == "accept, content-type"
        )

    def test_get_dont_expose_headers(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_all_origins=True,
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        app(environ, start_response)
        assert ACCESS_CONTROL_EXPOSE_HEADERS not in start_response.get_headers()

    def test_get_allow_credentials(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origins=["https://example.com"],
            cors_allow_credentials=True,
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        app(environ, start_response)
        assert start_response.get_headers()[ACCESS_CONTROL_ALLOW_CREDENTIALS] == "true"

    def test_get_allow_credentials_bad_origin(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origins=["https://example.com"],
            cors_allow_credentials=True,
        )
        environ["HTTP_ORIGIN"] = "https://example.org"
        app(environ, start_response)
        assert ACCESS_CONTROL_ALLOW_CREDENTIALS not in start_response.get_headers()

    def test_get_allow_credentials_disabled(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origins=["https://example.com"],
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        app(environ, start_response)
        assert ACCESS_CONTROL_ALLOW_CREDENTIALS not in start_response.get_headers()

    def test_allow_private_network_added_if_enabled_and_requested(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_private_network=True,
            cors_allow_all_origins=True,
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_PRIVATE_NETWORK"] = "true"
        environ["HTTP_ORIGIN"] = "http://example.com"
        app(environ, start_response)
        assert (
            start_response.get_headers()[ACCESS_CONTROL_ALLOW_PRIVATE_NETWORK] == "true"
        )

    def test_allow_private_network_not_added_if_enabled_and_not_requested(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_private_network=True,
            cors_allow_all_origins=True,
        )
        environ["HTTP_ORIGIN"] = "http://example.com"
        app(environ, start_response)
        assert ACCESS_CONTROL_ALLOW_PRIVATE_NETWORK not in start_response.get_headers()

    def test_allow_private_network_not_added_if_enabled_and_no_cors_origin(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_private_network=True,
            cors_allowed_origins=["http://example.com"],
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_PRIVATE_NETWORK"] = "true"
        environ["HTTP_ORIGIN"] = "http://example.org"
        app(environ, start_response)
        assert ACCESS_CONTROL_ALLOW_PRIVATE_NETWORK not in start_response.get_headers()

    def test_allow_private_network_not_added_if_disabled_and_requested(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_private_network=False,
            cors_allow_all_origins=True,
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_PRIVATE_NETWORK"] = "true"
        environ["HTTP_ORIGIN"] = "http://example.com"
        app(environ, start_response)
        assert ACCESS_CONTROL_ALLOW_PRIVATE_NETWORK not in start_response.get_headers()

    def test_options_allowed_origin(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_headers=["content-type"],
            cors_allow_methods=["GET", "OPTIONS"],
            cors_preflight_max_age=1002,
            cors_allow_all_origins=True,
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)

        headers = start_response.get_headers()

        assert start_response.status == "200 OK"
        assert headers[ACCESS_CONTROL_ALLOW_HEADERS] == "content-type"
        assert headers[ACCESS_CONTROL_ALLOW_METHODS] == "GET, OPTIONS"
        assert headers[ACCESS_CONTROL_MAX_AGE] == "1002"

    def test_options_no_max_age(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_headers=["content-type"],
            cors_allow_methods=["GET", "OPTIONS"],
            cors_preflight_max_age=0,
            cors_allow_all_origins=True,
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)

        headers = start_response.get_headers()
        assert headers[ACCESS_CONTROL_ALLOW_HEADERS] == "content-type"
        assert headers[ACCESS_CONTROL_ALLOW_METHODS] == "GET, OPTIONS"
        assert ACCESS_CONTROL_MAX_AGE not in headers

    def test_options_allowed_origins_with_port(self):
        app, environ, start_response = setup(
            **self.middleware, cors_allowed_origins=["https://localhost:9000"]
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["HTTP_ORIGIN"] = "https://localhost:9000"
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)

        assert (
            start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN]
            == "https://localhost:9000"
        )

    def test_options_adds_origin_when_domain_found_in_allowed_regexes(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origin_regexes=[r"^https://\w+\.example\.com$"],
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["HTTP_ORIGIN"] = "https://foo.example.com"
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)

        assert (
            start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN]
            == "https://foo.example.com"
        )

    def test_options_adds_origin_when_domain_found_in_allowed_regexes_second(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origin_regexes=[
                r"^https://\w+\.example\.org$",
                r"^https://\w+\.example\.com$",
            ],
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["HTTP_ORIGIN"] = "https://foo.example.com"
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)

        assert (
            start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN]
            == "https://foo.example.com"
        )

    def test_options_doesnt_add_origin_when_domain_not_found_in_allowed_regexes(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origin_regexes=[r"^https://\w+\.example\.org$"],
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["HTTP_ORIGIN"] = "https://foo.example.com"
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)

        assert ACCESS_CONTROL_ALLOW_ORIGIN not in start_response.get_headers()

    def test_options_empty_request_method(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_all_origins=True,
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = ""
        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)

        assert start_response.status == "200 OK"

    def test_options_no_headers(self):
        app, environ, start_response = setup(
            **self.middleware, cors_allow_all_origins=True, routes=[("/", text_view)]
        )
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)
        assert start_response.status == "405 Method Not Allowed"

    def test_allow_all_origins_get(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_credentials=True,
            cors_allow_all_origins=True,
            routes=[("/", text_view)],
        )
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["REQUEST_METHOD"] = "GET"
        app(environ, start_response)

        assert start_response.status == "200 OK"
        assert (
            start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN]
            == "https://example.com"
        )
        assert start_response.get_headers()["vary"] == "origin"

    def test_allow_all_origins_options(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_credentials=True,
            cors_allow_all_origins=True,
            routes=[("/", text_view)],
        )

        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)

        assert start_response.status == "200 OK"
        assert (
            start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN]
            == "https://example.com"
        )
        assert start_response.get_headers()["vary"] == "origin"

    def test_non_200_headers_still_set(self):
        """
        It's not clear whether the header should still be set for non-HTTP200
        when not a preflight request. However, this is the existing behavior for
        django-cors-middleware, and Spiderweb should mirror it.
        """
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_credentials=True,
            cors_allow_all_origins=True,
            routes=[("/unauthorized", unauthorized_view)],
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["PATH_INFO"] = "/unauthorized"
        app(environ, start_response)

        assert start_response.status == "401 Unauthorized"
        assert (
            start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN]
            == "https://example.com"
        )

    def test_auth_view_options(self):
        """
        Ensure HTTP200 and header still set, for preflight requests to views requiring
        authentication. See: https://github.com/adamchainz/django-cors-headers/issues/3
        """
        app, environ, start_response = setup(
            **self.middleware,
            cors_allow_credentials=True,
            cors_allow_all_origins=True,
            routes=[("/unauthorized", unauthorized_view)],
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["PATH_INFO"] = "/unauthorized"
        environ["REQUEST_METHOD"] = "OPTIONS"
        app(environ, start_response)

        assert start_response.status == "200 OK"
        assert (
            start_response.get_headers()[ACCESS_CONTROL_ALLOW_ORIGIN]
            == "https://example.com"
        )
        assert start_response.get_headers()["content-length"] == "0"

    def test_get_short_circuit(self):
        """
        Test a scenario when a middleware that returns a response is run before
        the `CorsMiddleware`. In this case
        `CorsMiddleware.process_response()` should ignore the request.
        """
        app, environ, start_response = setup(
            middleware=[
                "spiderweb.tests.middleware.InterruptingMiddleware",
                "spiderweb.middleware.cors.CorsMiddleware",
            ],
            cors_allow_credentials=True,
            cors_allowed_origins=["https://example.com"],
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        app(environ, start_response)

        assert ACCESS_CONTROL_ALLOW_ORIGIN not in start_response.get_headers()

    def test_get_short_circuit_should_be_ignored(self):
        app, environ, start_response = setup(
            middleware=[
                "spiderweb.tests.middleware.InterruptingMiddleware",
                "spiderweb.middleware.cors.CorsMiddleware",
            ],
            cors_urls_regex=r"^/foo/$",
            cors_allowed_origins=["https://example.com"],
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        app(environ, start_response)

        assert ACCESS_CONTROL_ALLOW_ORIGIN not in start_response.get_headers()

    def test_get_regex_matches(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_urls_regex=r"^/foo$",
            cors_allowed_origins=["https://example.com"],
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["PATH_INFO"] = "/foo"
        environ["REQUEST_METHOD"] = "GET"
        app(environ, start_response)

        assert ACCESS_CONTROL_ALLOW_ORIGIN in start_response.get_headers()

    def test_get_regex_doesnt_match(self):
        app, environ, start_response = setup(
            **self.middleware,
            cors_urls_regex=r"^/not-foo/$",
            cors_allowed_origins=["https://example.com"],
        )
        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "GET"
        environ["PATH_INFO"] = "/foo"
        environ["REQUEST_METHOD"] = "GET"
        app(environ, start_response)

        assert ACCESS_CONTROL_ALLOW_ORIGIN not in start_response.get_headers()

    def test_works_if_view_deletes_cors_enabled(self):
        """
        Just in case something crazy happens in the view or other middleware,
        check that get_response doesn't fall over if `_cors_enabled` is removed
        """

        def yeet(request):
            del request._cors_enabled
            return HttpResponse("hahaha")

        app, environ, start_response = setup(
            **self.middleware,
            cors_allowed_origins=["https://example.com"],
            routes=[("/yeet", yeet)],
        )

        environ["HTTP_ORIGIN"] = "https://example.com"
        environ["PATH_INFO"] = "/yeet"
        environ["REQUEST_METHOD"] = "GET"
        app(environ, start_response)

        assert ACCESS_CONTROL_ALLOW_ORIGIN in start_response.get_headers()
