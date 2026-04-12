import asyncio
import time
import uuid

from spiderweb.exceptions import UnusedMiddleware
from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse


class AsyncTimingMiddleware(SpiderwebMiddleware):
    """Measures wall-clock time for each request and adds it as a response header."""

    async def process_request(self, request: Request) -> None:
        request._start_time = time.monotonic()

    async def process_response(self, request: Request, response: HttpResponse) -> None:
        if hasattr(request, "_start_time"):
            elapsed_ms = (time.monotonic() - request._start_time) * 1000
            response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"


class AsyncRequestIdMiddleware(SpiderwebMiddleware):
    """Stamps each request with a unique ID, visible in both request and response."""

    async def process_request(self, request: Request) -> None:
        request.request_id = str(uuid.uuid4())

    async def process_response(self, request: Request, response: HttpResponse) -> None:
        if hasattr(request, "request_id"):
            response.headers["X-Request-Id"] = request.request_id


class AsyncEchoHeaderMiddleware(SpiderwebMiddleware):
    """Echoes the incoming X-Echo header back on the response, if present."""

    async def process_request(self, request: Request) -> None:
        # Store it so process_response can see it even if the handler changed things
        request._echo = request.META.get("HTTP_X_ECHO")

    async def process_response(self, request: Request, response: HttpResponse) -> None:
        if getattr(request, "_echo", None):
            response.headers["X-Echo"] = request._echo


class AsyncUppercasePostProcess(SpiderwebMiddleware):
    """
    Toy post-processing middleware: upper-cases responses for paths under /shout/.
    Demonstrates async post_process using a non-blocking await.
    """

    async def post_process(
        self, request: Request, response: HttpResponse, rendered_response: str | bytes
    ) -> str | bytes:
        if request.path.startswith("/shout"):
            # Simulate a trivial async step (e.g., fetching a transform config)
            await asyncio.sleep(0)
            if isinstance(rendered_response, bytes):
                return rendered_response.upper()
            return rendered_response.upper()
        return rendered_response


class SyncFlagMiddleware(SpiderwebMiddleware):
    """
    Plain synchronous middleware mixed into an async pipeline.
    Proves that sync middleware works unchanged alongside async middleware.
    """

    def process_request(self, request: Request) -> None:
        request.sync_flag = True

    def process_response(self, request: Request, response: HttpResponse) -> None:
        if getattr(request, "sync_flag", False):
            response.headers["X-Sync-Middleware"] = "active"


class UnusedAsyncMiddleware(SpiderwebMiddleware):
    """Self-removes from the pipeline on first call."""

    async def process_request(self, request: Request) -> None:
        raise UnusedMiddleware("This middleware does nothing and removes itself.")
