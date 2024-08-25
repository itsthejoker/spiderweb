from datetime import datetime, timedelta
import json

from peewee import CharField, TextField, DateTimeField, BooleanField

from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse
from spiderweb.db import SpiderwebModel
from spiderweb.utils import generate_key, is_jsonable


class Session(SpiderwebModel):
    session_key = CharField(max_length=64)
    csrf_token = CharField(max_length=64, null=True)
    user_id = CharField(max_length=64, null=True)
    session_data = TextField()
    created_at = DateTimeField()
    last_active = DateTimeField()
    ip_address = CharField(max_length=30)
    user_agent = TextField()

    class Meta:
        table_name = 'spiderweb_sessions'


class SessionMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request):
        existing_session = (
            Session.select()
            .where(
                Session.session_key
                == request.COOKIES.get(self.server.session_cookie_name),
                Session.ip_address == request.META.get("client_address"),
                Session.user_agent == request.headers.get("HTTP_USER_AGENT"),
            )
            .first()
        )
        new_session = False
        if not existing_session:
            new_session = True
        elif datetime.now() - existing_session.created_at > timedelta(
            seconds=self.server.session_max_age
        ):
            existing_session.delete_instance()
            new_session = True

        if new_session:
            request.SESSION = {}
            request._session["id"] = generate_key()
            request._session["new_session"] = True
            request.META["SESSION"] = None
            return

        request.SESSION = json.loads(existing_session.session_data)
        request.META["SESSION"] = existing_session
        request._session["id"] = existing_session.session_key
        existing_session.save()

    def process_response(self, request: Request, response: HttpResponse):
        cookie_settings = {
            "max_age": self.server.session_max_age,
            "same_site": self.server.session_cookie_same_site,
            "http_only": self.server.session_cookie_http_only,
            "secure": self.server.session_cookie_secure
            or request.META.get("HTTPS", False),
            "path": self.server.session_cookie_path,
        }

        # if a new session has been requested, ignore everything else and make that happen
        if request._session["new_session"]:
            # we generated a new one earlier, so we can use it now
            session_key = request._session["id"]
            response.set_cookie(
                self.server.session_cookie_name,
                session_key,
                **cookie_settings,
            )
            session = Session(
                session_key=session_key,
                session_data=json.dumps(request.SESSION),
                created_at=datetime.now(),
                last_active=datetime.now(),
                ip_address=request.META.get("client_address"),
                user_agent=request.headers.get("HTTP_USER_AGENT"),
            )
            session.save()
            return

        # Otherwise, we can save the one we already have.
        session_key = request.META["SESSION"].session_key
        # update the session expiration time
        response.set_cookie(
            self.server.session_cookie_name,
            session_key,
            **cookie_settings,
        )

        session = request.META["SESSION"]
        if not session:
            if not is_jsonable(request.SESSION):
                raise ValueError("Session data is not JSON serializable.")
            session = Session(
                session_key=session_key,
                session_data=json.dumps(request.SESSION),
                created_at=datetime.now(),
                last_active=datetime.now(),
                ip_address=request.META.get("client_address"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )
        else:
            session.session_data = json.dumps(request.SESSION)
            session.last_active = datetime.now()
        session.save()
