from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse, RedirectResponse


class TestMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> HttpResponse | None:
        # example of a middleware that sets a flag on the request
        request.spiderweb = True

    def process_response(
        self, request: Request, response: HttpResponse
    ) -> HttpResponse | None:
        # example of a middleware that sets a header on the resp
        if hasattr(request, "spiderweb"):
            response.headers["X-Spiderweb"] = "true"


class RedirectMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> HttpResponse | None:
        if request.path == "/middleware":
            return RedirectResponse("/")
