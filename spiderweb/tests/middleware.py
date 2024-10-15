from spiderweb import SpiderwebMiddleware, Request, HttpResponse, UnusedMiddleware


class ExplodingRequestMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> HttpResponse | None:
        raise UnusedMiddleware("Boom!")


class ExplodingResponseMiddleware(SpiderwebMiddleware):
    def process_response(
        self, request: Request, response: HttpResponse
    ) -> HttpResponse | None:
        raise UnusedMiddleware("Unfinished!")


class InterruptingMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> HttpResponse:
        return HttpResponse("Moo!")


class PostProcessingMiddleware(SpiderwebMiddleware):
    def post_process(self, request: Request, response: str) -> str:
        return response + " Moo!"
