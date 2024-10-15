import random

from spiderweb import ConfigError
from spiderweb.exceptions import UnusedMiddleware
from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse, RedirectResponse


class TestMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> None:
        # example of a middleware that sets a flag on the request
        request.spiderweb = True

    def process_response(self, request: Request, response: HttpResponse) -> None:
        # example of a middleware that sets a header on the resp
        if hasattr(request, "spiderweb"):
            response.headers["X-Spiderweb"] = "true"


class RedirectMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> HttpResponse:
        if request.path == "/middleware":
            return RedirectResponse("/")


class ExplodingMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> HttpResponse | None:
        raise UnusedMiddleware("Unfinished!")


class CaseTransformMiddleware(SpiderwebMiddleware):
    # this breaks everything, but it's hilarious so it's worth it.
    # Blame Sam.
    def post_process(self, request: Request, rendered_response: str) -> str:
        valid_options = ["spongebob", "random"]
        method = self.server.extra_data.get("case_transform_middleware_type", "spongebob")
        if method not in valid_options:
            raise ConfigError(
                f"Invalid method '{method}' for CaseTransformMiddleware."
                f" Valid options are {', '.join(valid_options)}"
            )

        if method == "spongebob":
            return "".join(
                char.upper() if i % 2 == 0 else char.lower() for i, char in enumerate(rendered_response)
            )
        else:
            return "".join(
                char.upper() if random.random() > 0.5 else char for char in rendered_response
            )
