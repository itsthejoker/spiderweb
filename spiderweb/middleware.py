from typing import Optional, NoReturn

from spiderweb.request import Request
from spiderweb.response import HttpResponse


class SpiderwebMiddleware:
    """
    All middleware should inherit from this class and have the following
    (optional!) methods:

    process_request(self, request) -> None or Response
    process_response(self, request, response) -> None

    Middleware can be used to modify requests and responses in a variety of ways.
    If one of the two methods is not defined, the request or response will be passed
    through unmodified.

    If `process_request` returns

    """
    def process_request(self, request: Request) -> HttpResponse | None:
        # example of a middleware that sets a flag on the request
        request.spiderweb = True


    def process_response(self, request: Request, response: HttpResponse) -> NoReturn:
        # example of a middleware that sets a header on the response
        if hasattr(request, 'spiderweb'):
            response['X-Spiderweb'] = 'true'
        return response
