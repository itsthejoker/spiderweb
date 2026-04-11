import asyncio
import inspect
from typing import Callable, ClassVar
import sys

from .base import SpiderwebMiddleware as SpiderwebMiddleware
from ..exceptions import ConfigError, UnusedMiddleware, StartupErrors
from ..request import Request
from ..response import HttpResponse
from ..utils import import_by_string


class MiddlewareMixin:
    """Cannot be called on its own. Requires context of SpiderwebRouter."""

    _middleware: list[str]
    middleware: list[ClassVar]
    fire_response: Callable

    def init_middleware(self):
        if self._middleware:
            middleware_by_reference = []
            for m in self._middleware:
                try:
                    middleware_by_reference.append(import_by_string(m)(server=self))
                except ImportError:
                    raise ConfigError(f"Middleware '{m}' not found.")
            self.middleware = middleware_by_reference

    def run_middleware_checks(self):
        errors = []
        for middleware in self.middleware:
            if hasattr(middleware, "checks"):
                for check in middleware.checks:
                    if issue := check(server=self).check():
                        errors.append(issue)

        if errors:
            # just show the messages
            sys.tracebacklimit = 1
            raise StartupErrors(
                "Problems were identified during startup — cannot continue.", errors
            )

    def process_request_middleware(self, request: Request) -> None | bool:
        for middleware in self.middleware:
            try:
                resp = middleware.process_request(request)
            except UnusedMiddleware:
                self.middleware.remove(middleware)
                continue
            if resp:
                self.process_response_middleware(request, resp)
                return resp  # abort further processing

    def process_response_middleware(
        self, request: Request, response: HttpResponse
    ) -> None:
        for middleware in reversed(self.middleware):
            try:
                middleware.process_response(request, response)
            except UnusedMiddleware:
                self.middleware.remove(middleware)
                continue

    def post_process_middleware(
        self, request: Request, response: HttpResponse, rendered_response: str
    ) -> str | bytes:
        # run them in reverse order, same as process_response. The top of the middleware
        # stack should be the first and last middleware to run.
        for middleware in reversed(self.middleware):
            try:
                rendered_response = middleware.post_process(
                    request, response, rendered_response
                )
            except UnusedMiddleware:
                self.middleware.remove(middleware)
                continue
        return rendered_response

    async def process_request_middleware_async(self, request: Request) -> None | HttpResponse:
        # Iterate over a snapshot so removals during the loop don't skip elements.
        # Do NOT call process_response_middleware_async here — the caller (_handle_http)
        # is responsible for running response middleware on the abort response.
        to_remove = []
        result = None
        for middleware in list(self.middleware):
            try:
                fn = middleware.process_request
                if inspect.iscoroutinefunction(fn):
                    resp = await fn(request)
                else:
                    resp = await asyncio.to_thread(fn, request)
            except UnusedMiddleware:
                to_remove.append(middleware)
                continue
            if resp:
                result = resp
                break
        for m in to_remove:
            try:
                self.middleware.remove(m)
            except ValueError:
                pass
        return result

    async def process_response_middleware_async(
        self, request: Request, response: HttpResponse
    ) -> None:
        to_remove = []
        for middleware in list(reversed(self.middleware)):
            try:
                fn = middleware.process_response
                if inspect.iscoroutinefunction(fn):
                    await fn(request, response)
                else:
                    await asyncio.to_thread(fn, request, response)
            except UnusedMiddleware:
                to_remove.append(middleware)
        for m in to_remove:
            try:
                self.middleware.remove(m)
            except ValueError:
                pass

    async def post_process_middleware_async(
        self, request: Request, response: HttpResponse, rendered: str
    ) -> str | bytes:
        to_remove = []
        for middleware in list(reversed(self.middleware)):
            try:
                fn = middleware.post_process
                if inspect.iscoroutinefunction(fn):
                    rendered = await fn(request, response, rendered)
                else:
                    rendered = await asyncio.to_thread(fn, request, response, rendered)
            except UnusedMiddleware:
                to_remove.append(middleware)
        for m in to_remove:
            try:
                self.middleware.remove(m)
            except ValueError:
                pass
        return rendered
