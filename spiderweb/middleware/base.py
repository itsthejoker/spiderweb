from spiderweb.request import Request
from spiderweb.response import HttpResponse


class SpiderwebMiddleware:
    """
    All middleware should inherit from this class and have the following
    (optional!) methods:

    process_request(self, request) -> None or Response
    process_response(self, request, resp) -> None

    Middleware can be used to modify requests and responses in a variety of ways.
    If one of the two methods is not defined, the request or resp will be passed
    through unmodified.

    If `process_request` returns a HttpResponse, the request will be short-circuited
    and the response will be returned immediately. `process_response` will not be called.
    """

    def __init__(self, server):
        self.server = server

    def process_request(self, request: Request) -> HttpResponse | None:
        pass

    def process_response(
        self, request: Request, response: HttpResponse
    ) -> HttpResponse | None:
        pass

    def on_error(self, request: Request, e: Exception) -> HttpResponse | None:
        pass
