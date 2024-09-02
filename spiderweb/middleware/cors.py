import re
from urllib.parse import urlsplit, SplitResult

from spiderweb.request import Request
from spiderweb.response import HttpResponse
from spiderweb.middleware import SpiderwebMiddleware

ACCESS_CONTROL_ALLOW_ORIGIN = "access-control-allow-origin"
ACCESS_CONTROL_EXPOSE_HEADERS = "access-control-expose-headers"
ACCESS_CONTROL_ALLOW_CREDENTIALS = "access-control-allow-credentials"
ACCESS_CONTROL_ALLOW_HEADERS = "access-control-allow-headers"
ACCESS_CONTROL_ALLOW_METHODS = "access-control-allow-methods"
ACCESS_CONTROL_MAX_AGE = "access-control-max-age"
ACCESS_CONTROL_REQUEST_PRIVATE_NETWORK = "access-control-request-private-network"
ACCESS_CONTROL_ALLOW_PRIVATE_NETWORK = "access-control-allow-private-network"


class CorsMiddleware(SpiderwebMiddleware):
    # heavily 'based' on https://github.com/adamchainz/django-cors-headers,
    # which is provided under the MIT license. This is essentially a direct
    # port, since django-cors-headers is battle-tested code that has been
    # around for a long time and it works well. Shoutouts to Otto, Adam, and
    # crew for helping make this a complete non-issue in Django for a very long
    # time.

    def is_enabled(self, request: Request):
        return bool(re.match(self.server.cors_urls_regex, request.path))

    def add_response_headers(self, request: Request, response: HttpResponse):
        enabled = getattr(request, "_cors_enabled", None)
        if enabled is None:
            enabled = self.is_enabled(request)

        if not enabled:
            return response

        if "vary" in response.headers:
            response.headers["vary"].append("origin")
        else:
            response.headers["vary"] = ["origin"]

        origin = request.headers.get("origin")
        if not origin:
            return response

        try:
            url = urlsplit(origin)
        except ValueError:
            return response

        if (
            not self.server.cors_allow_all_origins
            and not self.origin_found_in_allow_lists(origin, url)
        ):
            return response

        if (
            self.server.cors_allow_all_origins
            and not self.server.cors_allow_credentials
        ):
            response.headers[ACCESS_CONTROL_ALLOW_ORIGIN] = "*"
        else:
            response.headers[ACCESS_CONTROL_ALLOW_ORIGIN] = origin

        if self.server.cors_allow_credentials:
            response.headers[ACCESS_CONTROL_ALLOW_CREDENTIALS] = "true"

        if len(self.server.cors_expose_headers):
            response.headers[ACCESS_CONTROL_EXPOSE_HEADERS] = ", ".join(
                self.server.cors_expose_headers
            )

        if request.method == "OPTIONS":
            response.headers[ACCESS_CONTROL_ALLOW_HEADERS] = ", ".join(
                self.server.cors_allow_headers
            )
            response.headers[ACCESS_CONTROL_ALLOW_METHODS] = ", ".join(
                self.server.cors_allow_methods
            )
            if self.server.cors_preflight_max_age:
                response.headers[ACCESS_CONTROL_MAX_AGE] = str(
                    self.server.cors_preflight_max_age
                )

        if (
            self.server.cors_allow_private_network
            and request.headers.get(ACCESS_CONTROL_REQUEST_PRIVATE_NETWORK) == "true"
        ):
            response.headers[ACCESS_CONTROL_ALLOW_PRIVATE_NETWORK] = "true"

        return response

    def origin_found_in_allow_lists(self, origin: str, url: SplitResult) -> bool:
        return (
            (origin == "null" and origin in self.server.cors_allowed_origins)
            or self._url_in_allowlist(url)
            or self.regex_domain_match(origin)
        )

    def _url_in_allowlist(self, url: SplitResult) -> bool:
        origins = [urlsplit(o) for o in self.server.cors_allowed_origins]
        return any(
            origin.scheme == url.scheme and origin.netloc == url.netloc
            for origin in origins
        )

    def regex_domain_match(self, origin: str) -> bool:
        return any(
            re.match(domain_pattern, origin)
            for domain_pattern in self.server.cors_allowed_origin_regexes
        )

    def process_request(self, request: Request) -> HttpResponse | None:
        # Identify and handle a preflight request
        # origin = request.META.get("HTTP_ORIGIN")
        request._cors_enabled = self.is_enabled(request)
        if (
            request._cors_enabled
            and request.method == "OPTIONS"
            and "access-control-request-method" in request.headers
        ):
            # this should be 204, but according to mozilla, not all browsers
            # parse that correctly. See [204] comment below.
            resp = HttpResponse(
                "",
                status_code=200,
                headers={"content-type": "text/plain", "content-length": 0},
            )
            self.add_response_headers(request, resp)
            return resp

    def process_response(
        self, request: Request, response: HttpResponse
    ) -> None:
        self.add_response_headers(request, response)

# [204]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/OPTIONS#status_code
