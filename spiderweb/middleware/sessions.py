from datetime import datetime, timedelta
import json

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped

from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse
from spiderweb.db import Base
from spiderweb.utils import generate_key, is_jsonable


class Session(Base):
    __tablename__ = "spiderweb_sessions"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    session_key: Mapped[str] = Column(String(64), index=True, nullable=False)
    csrf_token: Mapped[str | None] = Column(String(64), nullable=True)
    user_id: Mapped[str | None] = Column(String(64), nullable=True)
    session_data: Mapped[str] = Column(Text, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, nullable=False)
    last_active: Mapped[datetime] = Column(DateTime, nullable=False)
    ip_address: Mapped[str] = Column(String(30), nullable=False)
    user_agent: Mapped[str] = Column(Text, nullable=False)


class SessionMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request):
        dbsession = self.server.get_db_session()
        try:
            existing_session = (
                dbsession.query(Session)
                .filter(
                    Session.session_key
                    == request.COOKIES.get(self.server.session_cookie_name),
                    Session.ip_address == request.META.get("client_address"),
                    Session.user_agent == request.headers.get("HTTP_USER_AGENT"),
                )
                .order_by(Session.id.desc())
                .first()
            )
            new_session = False
            if not existing_session:
                new_session = True
            elif datetime.now() - existing_session.created_at > timedelta(
                seconds=self.server.session_max_age
            ):
                dbsession.delete(existing_session)
                dbsession.commit()
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
            # touch last_active
            existing_session.last_active = datetime.now()
            dbsession.add(existing_session)
            dbsession.commit()
        finally:
            dbsession.close()

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
        if request._session["new_session"] is True:
            # we generated a new one earlier, so we can use it now
            session_key = request._session["id"]
            response.set_cookie(
                self.server.session_cookie_name,
                session_key,
                **cookie_settings,
            )
            if not is_jsonable(request.SESSION):
                raise ValueError("Session data is not JSON serializable.")
            dbsession = self.server.get_db_session()
            try:
                session = Session(
                    session_key=session_key,
                    session_data=json.dumps(request.SESSION),
                    created_at=datetime.now(),
                    last_active=datetime.now(),
                    ip_address=request.META.get("client_address"),
                    user_agent=request.headers.get("HTTP_USER_AGENT"),
                )
                dbsession.add(session)
                dbsession.commit()
            finally:
                dbsession.close()
            return

        # Otherwise, we can save the one we already have.
        # Use the cached session id to avoid touching a detached SQLAlchemy instance.
        session_key = request._session["id"]
        # update the session expiration time
        response.set_cookie(
            self.server.session_cookie_name,
            session_key,
            **cookie_settings,
        )

        dbsession = self.server.get_db_session()
        try:
            session = (
                dbsession.query(Session)
                .filter(Session.session_key == session_key)
                .order_by(Session.id.desc())
                .first()
            )
            if session:
                session.session_data = json.dumps(request.SESSION)
                session.last_active = datetime.now()
                dbsession.add(session)
                dbsession.commit()
        finally:
            dbsession.close()
