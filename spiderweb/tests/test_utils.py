import re

import pytest

from spiderweb.utils import (
    Headers,
    convert_url_to_regex,
    generate_key,
    get_client_address,
    get_http_status_by_code,
    import_by_string,
    is_form_request,
    is_jsonable,
    is_safe_path,
)

# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


class TestHeaders:
    def test_setitem_normalizes_dashes_to_underscores(self):
        h = Headers()
        h["Content-Type"] = "text/html"
        # Should be stored as content_type
        assert dict.__contains__(h, "content_type")

    def test_setitem_lowercases_key(self):
        h = Headers()
        h["X-Custom-Header"] = "val"
        assert dict.__contains__(h, "x_custom_header")

    def test_getitem_normalizes_key(self):
        h = Headers()
        h["Content-Type"] = "text/html"
        assert h["Content-Type"] == "text/html"
        assert h["content-type"] == "text/html"
        assert h["content_type"] == "text/html"

    def test_getitem_falls_back_to_http_prefix(self):
        # If the plain key is missing, the http_ variant should be found
        h = Headers()
        dict.__setitem__(h, "http_host", "example.com")
        assert h["host"] == "example.com"

    def test_getitem_direct_key_wins_over_http_prefix(self):
        h = Headers()
        h["host"] = "direct"
        dict.__setitem__(h, "http_host", "indirect")
        assert h["host"] == "direct"

    def test_contains_plain_key(self):
        h = Headers()
        h["Content-Type"] = "text/html"
        assert "Content-Type" in h
        assert "content-type" in h
        assert "content_type" in h

    def test_contains_http_prefix_fallback(self):
        h = Headers()
        dict.__setitem__(h, "http_host", "localhost")
        assert "host" in h

    def test_not_contains_missing_key(self):
        h = Headers()
        assert "x-missing" not in h

    def test_get_existing_key(self):
        h = Headers()
        h["accept"] = "application/json"
        assert h.get("accept") == "application/json"

    def test_get_returns_default_for_missing(self):
        h = Headers()
        assert h.get("x-nonexistent", "fallback") == "fallback"
        assert h.get("x-nonexistent") is None

    def test_get_falls_back_to_http_prefix(self):
        h = Headers()
        dict.__setitem__(h, "http_accept", "text/plain")
        assert h.get("accept") == "text/plain"

    def test_setdefault_sets_when_absent(self):
        h = Headers()
        result = h.setdefault("x-foo", "bar")
        assert result == "bar"

    def test_setdefault_lowercases_key(self):
        h = Headers()
        h.setdefault("X-Custom", "value")
        assert dict.__contains__(h, "x-custom")


# ---------------------------------------------------------------------------
# import_by_string
# ---------------------------------------------------------------------------


class TestImportByString:
    def test_import_valid_class(self):
        from spiderweb.response import HttpResponse

        klass = import_by_string("spiderweb.response.HttpResponse")
        assert klass is HttpResponse

    def test_import_valid_function(self):
        from spiderweb.utils import generate_key

        fn = import_by_string("spiderweb.utils.generate_key")
        assert fn is generate_key

    def test_invalid_module_raises(self):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            import_by_string("nonexistent_package_xyz.SomeClass")

    def test_invalid_attribute_raises(self):
        with pytest.raises(AttributeError):
            import_by_string("spiderweb.response.NoSuchClass")


# ---------------------------------------------------------------------------
# is_safe_path
# ---------------------------------------------------------------------------


class TestIsSafePath:
    def test_normal_path_is_safe(self):
        assert is_safe_path("/some/normal/path") is True

    def test_path_with_dotdot_is_unsafe(self):
        assert is_safe_path("/some/../path") is False

    def test_relative_traversal_is_unsafe(self):
        assert is_safe_path("../../etc/passwd") is False

    def test_dotdot_at_start(self):
        assert is_safe_path("../secret") is False

    def test_single_dot_is_safe(self):
        assert is_safe_path("/a/./b") is True


# ---------------------------------------------------------------------------
# get_client_address
# ---------------------------------------------------------------------------


class TestGetClientAddress:
    def test_uses_last_entry_in_x_forwarded_for(self):
        environ = {"HTTP_X_FORWARDED_FOR": "10.0.0.1, 192.168.1.1"}
        assert get_client_address(environ) == "192.168.1.1"

    def test_single_ip_in_x_forwarded_for(self):
        environ = {"HTTP_X_FORWARDED_FOR": "10.0.0.1"}
        assert get_client_address(environ) == "10.0.0.1"

    def test_falls_back_to_remote_addr(self):
        assert get_client_address({"REMOTE_ADDR": "127.0.0.1"}) == "127.0.0.1"

    def test_unknown_when_both_missing(self):
        assert get_client_address({}) == "unknown"


# ---------------------------------------------------------------------------
# generate_key
# ---------------------------------------------------------------------------


class TestGenerateKey:
    def test_default_length_is_64(self):
        assert len(generate_key()) == 64

    def test_custom_length(self):
        assert len(generate_key(32)) == 32

    def test_keys_are_alphanumeric(self):
        import string

        valid = set(string.ascii_letters + string.digits)
        for _ in range(5):
            assert all(c in valid for c in generate_key())

    def test_keys_are_unique(self):
        keys = {generate_key() for _ in range(10)}
        assert len(keys) == 10


# ---------------------------------------------------------------------------
# is_jsonable
# ---------------------------------------------------------------------------


class TestIsJsonable:
    def test_dict_is_jsonable(self):
        assert is_jsonable({"a": 1}) is True

    def test_string_is_jsonable(self):
        assert is_jsonable("hello") is True

    def test_list_is_jsonable(self):
        assert is_jsonable([1, 2, 3]) is True

    def test_none_is_jsonable(self):
        assert is_jsonable(None) is True

    def test_arbitrary_object_not_jsonable(self):
        assert is_jsonable(object()) is False

    def test_lambda_not_jsonable(self):
        assert is_jsonable(lambda: None) is False


# ---------------------------------------------------------------------------
# convert_url_to_regex
# ---------------------------------------------------------------------------


class TestConvertUrlToRegex:
    def test_compiled_pattern_returned_unchanged(self):
        pattern = re.compile(r"^/test$")
        result = convert_url_to_regex(pattern)
        assert result is pattern

    def test_string_dots_are_escaped(self):
        result = convert_url_to_regex("example.com")
        # The dot must match a literal dot, not any char
        assert result.match("example.com") is not None
        assert not result.match("exampleXcom")

    def test_wildcard_becomes_dot_plus(self):
        result = convert_url_to_regex("*.example.com")
        assert result.match("sub.example.com") is not None

    def test_plain_string_compiles(self):
        result = convert_url_to_regex("localhost")
        assert result.match("localhost") is not None


# ---------------------------------------------------------------------------
# get_http_status_by_code
# ---------------------------------------------------------------------------


class TestGetHttpStatusByCode:
    def test_200(self):
        assert get_http_status_by_code(200) == "200 OK"

    def test_404(self):
        assert get_http_status_by_code(404) == "404 Not Found"

    def test_500(self):
        assert get_http_status_by_code(500) == "500 Internal Server Error"

    def test_invalid_code_raises(self):
        with pytest.raises(ValueError):
            get_http_status_by_code(999)


# ---------------------------------------------------------------------------
# is_form_request (utils standalone version)
# ---------------------------------------------------------------------------


class TestIsFormRequest:
    def _make_request(self, content_type=None):
        """Return a minimal object with .headers containing Content-Type."""

        class FakeRequest:
            headers = Headers()

        req = FakeRequest()
        if content_type is not None:
            req.headers["Content-Type"] = content_type
        return req

    def test_returns_true_for_form_urlencoded(self):
        req = self._make_request("application/x-www-form-urlencoded")
        assert is_form_request(req) is True

    def test_returns_false_for_json(self):
        req = self._make_request("application/json")
        assert is_form_request(req) is False

    def test_returns_false_when_no_content_type(self):
        req = self._make_request()
        assert is_form_request(req) is False
