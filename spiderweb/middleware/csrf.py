import re
from re import Pattern
from datetime import datetime, timedelta
from typing import Optional

from spiderweb.exceptions import CSRFError, ConfigError
from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse
from spiderweb.server_checks import ServerCheck


class CheckForSessionMiddleware(ServerCheck):
    SESSION_MIDDLEWARE_NOT_FOUND = (
        "Session middleware is not enabled. It must be listed above"
        "CSRFMiddleware in the middleware list."
    )

    def check(self) -> Optional[Exception]:
        if (
            "spiderweb.middleware.sessions.SessionMiddleware"
            not in self.server._middleware
        ):
            return ConfigError(self.SESSION_MIDDLEWARE_NOT_FOUND)


class VerifyCorrectMiddlewarePlacement(ServerCheck):
    SESSION_MIDDLEWARE_BELOW_CSRF = (
        "SessionMiddleware is enabled, but it must be listed above"
        "CSRFMiddleware in the middleware list."
    )

    def check(self) -> Optional[Exception]:
        if (
            "spiderweb.middleware.sessions.SessionMiddleware"
            not in self.server._middleware
        ):
            # this is handled by CheckForSessionMiddleware
            return

        if self.server._middleware.index(
            "spiderweb.middleware.sessions.SessionMiddleware"
        ) > self.server._middleware.index("spiderweb.middleware.csrf.CSRFMiddleware"):
            return ConfigError(self.SESSION_MIDDLEWARE_BELOW_CSRF)


class VerifyCorrectFormatForTrustedOrigins(ServerCheck):
    CSRF_TRUSTED_ORIGINS_IS_LIST_OF_STR = (
        "The csrf_trusted_origins setting must be a list of strings."
    )

    def check(self) -> Optional[Exception]:
        if not isinstance(self.server.csrf_trusted_origins, list):
            return ConfigError(self.CSRF_TRUSTED_ORIGINS_IS_LIST_OF_STR)

        for item in self.server.csrf_trusted_origins:
            if not isinstance(item, Pattern):
                # It's a pattern here because we've already manipulated it
                # by the time this check runs
                return ConfigError(self.CSRF_TRUSTED_ORIGINS_IS_LIST_OF_STR)


class CSRFMiddleware(SpiderwebMiddleware):

    checks = [
        CheckForSessionMiddleware,
        VerifyCorrectMiddlewarePlacement,
        VerifyCorrectFormatForTrustedOrigins,
    ]

    CSRF_EXPIRY = 60 * 60  # 1 hour

    def is_trusted_origin(self, request) -> bool:
        origin = request.headers.get("http_origin")
        referrer = request.headers.get("http_referer") or request.headers.get(
            "http_referrer"
        )
        host = request.headers.get("http_host")

        if not origin and not (host == referrer):
            return False

        if not origin and (host == referrer):
            origin = host

        for re_origin in self.server.csrf_trusted_origins:
            if re.match(re_origin, origin):
                return True
        return False

    def process_request(self, request: Request) -> HttpResponse | None:
        if request.method == "POST":
            if hasattr(request.handler, "csrf_exempt"):
                if request.handler.csrf_exempt is True:
                    return

            csrf_token = (
                request.headers.get("x-csrf-token")
                or request.GET.get("csrf_token")
                or request.POST.get("csrf_token")
            )

            if not self.is_trusted_origin(request):
                if self.is_csrf_valid(request, csrf_token):
                    return None
                else:
                    raise CSRFError()
        return None

    def process_response(self, request: Request, response: HttpResponse) -> None:
        token = self.get_csrf_token(request)
        # do we need it in both places?
        response.headers["x-csrf-token"] = token
        response.context |= {
            "csrf_token": f"""<input type="hidden" name="csrf_token" value="{token}">""",
            "raw_csrf_token": token,  # in case they want to format it themselves
        }

    def get_csrf_token(self, request):
        # the session key should be here because we've processed the session first
        session_key = request._session["id"]
        return self.server.encrypt(
            f"{str(datetime.now().isoformat())}::{session_key}"
        ).decode(self.server.DEFAULT_ENCODING)

    def is_csrf_valid(self, request, key):
        try:
            decoded = self.server.decrypt(key)
            timestamp, session_key = decoded.split("::")
            if session_key != request._session["id"]:
                return False
            if datetime.now() - timedelta(
                seconds=self.CSRF_EXPIRY
            ) > datetime.fromisoformat(timestamp):
                return False
            return True
        except Exception:
            return False
