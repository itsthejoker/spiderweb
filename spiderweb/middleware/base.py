from spiderweb.request import Request
from spiderweb.response import HttpResponse


class SpiderwebMiddleware:
    """
    All middleware should inherit from this class and have the following
    (optional!) methods:

    process_request(self, request) -> None or Response
    process_response(self, request, resp) -> None
    on_error(self, request, e) -> Response
    post_process(self, request, resp) -> Response

    Middleware can be used to modify requests and responses in a variety of ways.
    If one of the two methods is not defined, the request or resp will be passed
    through unmodified.

    If `process_request` returns a HttpResponse, the request will be short-circuited
    and the response will be returned immediately. `process_response` will not be called.
    """

    def __init__(self, server):
        self.server = server

    def process_request(self, request: Request) -> HttpResponse | None:
        # This method is called before the request is passed to the view. You can safely
        # modify the request in this method, or return an HttpResponse to short-circuit
        # the request and return a response immediately.
        pass

    def process_response(
        self, request: Request, response: HttpResponse
    ) -> None:
        # This method is called after the view has returned a response. You can modify
        # the response in this method. The response will be returned to the client after
        # all middleware has been processed.
        pass

    def on_error(self, request: Request, e: Exception) -> HttpResponse | None:
        # This method is called if an exception is raised during the request. You can
        # return a response here to handle the error. If you return None, the exception
        # will be re-raised.
        pass

    def post_process(self, request: Request, rendered_response: str) -> str:
        # This method is called after all the middleware has been processed and receives
        # the final rendered response in str form. You can modify the response here.
        return rendered_response
