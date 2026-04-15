from typing import Optional

from spiderweb.models import User, AnonymousUser
from spiderweb.request import Request
from spiderweb.utils import generate_key


def authenticate(
    request: Request, username: str = "", password: str = "", **kwargs
) -> Optional[User]:
    if not username or not password:
        return None

    db = request.server.get_db_session()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user and user.check_password(password):
            return user
        return None
    finally:
        db.close()


def login(request: Request, user: User) -> None:
    if not hasattr(request, "SESSION"):
        request.SESSION = {}

    request.SESSION["_auth_user_id"] = str(user.id)
    if hasattr(request, "user"):
        request.user = user


def logout(request: Request) -> None:
    request.SESSION = {}
    if hasattr(request, "_session"):
        request._session["new_session"] = True
        request._session["id"] = generate_key()

    if hasattr(request, "user"):
        request.user = AnonymousUser()
