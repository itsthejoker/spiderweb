from datetime import datetime, timedelta

from spiderweb.exceptions import CSRFError, ConfigError
from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse
from spiderweb.server_checks import ServerCheck


class SessionCheck(ServerCheck):

    SESSION_MIDDLEWARE_NOT_FOUND = (
        "Session middleware is not enabled. It must be listed above"
        "CSRFMiddleware in the middleware list."
    )
    SESSION_MIDDLEWARE_BELOW_CSRF = (
        "SessionMiddleware is enabled, but it must be listed above"
        "CSRFMiddleware in the middleware list."
    )

    def check(self):

        if (
            "spiderweb.middleware.sessions.SessionMiddleware"
            not in self.server._middleware
        ):
            raise ConfigError(self.SESSION_MIDDLEWARE_NOT_FOUND)

        if self.server._middleware.index(
            "spiderweb.middleware.sessions.SessionMiddleware"
        ) > self.server._middleware.index(
            "spiderweb.middleware.csrf.CSRFMiddleware"
        ):
            raise ConfigError(self.SESSION_MIDDLEWARE_BELOW_CSRF)


class CSRFMiddleware(SpiderwebMiddleware):

    checks = [SessionCheck]

    CSRF_EXPIRY = 60 * 60  # 1 hour

    def process_request(self, request: Request) -> HttpResponse | None:
        if request.method == "POST":
            if hasattr(request.handler, "csrf_exempt"):
                if request.handler.csrf_exempt is True:
                    return
            csrf_token = (
                request.headers.get("X-CSRF-TOKEN")
                or request.GET.get("csrf_token")
                or request.POST.get("csrf_token")
            )
            if self.is_csrf_valid(request, csrf_token):
                return None
            else:
                raise CSRFError()
        return None

    def process_response(self, request: Request, response: HttpResponse) -> None:
        token = self.get_csrf_token(request)
        # do we need it in both places?
        response.headers["X-CSRF-TOKEN"] = token
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
