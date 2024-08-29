from spiderweb import SpiderwebMiddleware, Request, HttpResponse, UnusedMiddleware


class ExplodingRequestMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> HttpResponse | None:
        raise UnusedMiddleware("Boom!")


class ExplodingResponseMiddleware(SpiderwebMiddleware):
    def process_response(
        self, request: Request, response: HttpResponse
    ) -> HttpResponse | None:
        raise UnusedMiddleware("Unfinished!")
