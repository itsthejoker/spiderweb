from datetime import datetime, timedelta

from spiderweb.exceptions import CSRFError
from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse


class CSRFMiddleware(SpiderwebMiddleware):
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
            if self.is_csrf_valid(csrf_token):
                return None
            else:
                raise CSRFError()
        return None

    def process_response(self, request: Request, response: HttpResponse) -> None:
        token = self.get_csrf_token()
        # do we need it in both places?
        response.headers["X-CSRF-TOKEN"] = token
        response.context |= {
            "csrf_token": f"""<input type="hidden" name="csrf_token" value="{token}">""",
            "raw_csrf_token": token,  # in case they want to format it themselves
        }

    def get_csrf_token(self):
        return self.server.encrypt(str(datetime.now().isoformat())).decode(
            self.server.DEFAULT_ENCODING
        )

    def is_csrf_valid(self, key):
        try:
            decoded = self.server.decrypt(key)
            if datetime.now() - timedelta(
                seconds=self.CSRF_EXPIRY
            ) > datetime.fromisoformat(decoded):
                return False
            return True
        except Exception:
            return False
