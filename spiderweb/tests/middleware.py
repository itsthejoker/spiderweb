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
    def post_process(
        self, request: Request, response: HttpResponse, rendered_response: str
    ) -> str:
        return rendered_response + " Moo!"


class PostProcessingWithHeaderManipulation(SpiderwebMiddleware):
    def post_process(
        self, request: Request, response: HttpResponse, rendered_response: str
    ) -> str:
        response.headers["X-Moo"] = "true"
        return rendered_response


class ExplodingPostProcessingMiddleware(SpiderwebMiddleware):
    def post_process(
        self, request: Request, response: HttpResponse, rendered_response: str
    ) -> str:
        raise UnusedMiddleware("Unfinished!")
