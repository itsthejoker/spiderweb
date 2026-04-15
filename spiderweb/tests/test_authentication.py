from spiderweb.authentication import authenticate, login, logout
from spiderweb.models.user import User, AnonymousUser
from spiderweb.tests.helpers import setup


def test_authenticate():
    app, environ, start_response = setup()
    db = app.get_db_session()
    user = User(
        username="testuser_auth",
        first_name="Test",
        last_name="User",
        email="test@example.com",
    )
    user.set_password("mypassword")
    db.add(user)
    db.commit()

    # Create dummy request
    from spiderweb.request import Request

    req = Request(environ=environ, server=app)

    # Valid auth
    auth_user = authenticate(req, username="testuser_auth", password="mypassword")
    assert auth_user is not None
    assert auth_user.username == "testuser_auth"

    # Invalid password
    auth_user = authenticate(req, username="testuser_auth", password="wrongpassword")
    assert auth_user is None

    # Invalid username
    auth_user = authenticate(req, username="wronguser", password="mypassword")
    assert auth_user is None

    # Empty credentials
    assert authenticate(req, username="", password="mypassword") is None
    assert authenticate(req, username="testuser", password="") is None
    assert authenticate(req) is None

    db.close()


def test_login():
    app, environ, start_response = setup()
    db = app.get_db_session()
    user = User(
        username="loginuser",
        first_name="Test",
        last_name="User",
        email="login@example.com",
    )
    user.set_password("mypassword")
    db.add(user)
    db.commit()

    from spiderweb.request import Request

    req = Request(environ=environ, server=app)
    req.user = None

    login(req, user)

    assert req.SESSION["_auth_user_id"] == str(user.id)
    assert req.user == user

    db.close()


def test_logout():
    app, environ, start_response = setup()
    from spiderweb.request import Request

    req = Request(environ=environ, server=app)

    req.SESSION = {"_auth_user_id": "1", "other_data": "value"}
    req.user = "dummy_user"
    old_session_id = req._session["id"]

    logout(req)

    assert req.SESSION == {}
    assert isinstance(req.user, AnonymousUser)
    assert req._session["new_session"] is True
    assert req._session["id"] != old_session_id


def test_login_missing_attributes():
    app, environ, start_response = setup()
    from spiderweb.request import Request

    req = Request(environ=environ, server=app)

    del req.SESSION

    user = User(id=999)
    login(req, user)

    assert req.SESSION["_auth_user_id"] == "999"
    assert not hasattr(req, "user")


def test_logout_missing_attributes():
    app, environ, start_response = setup()
    from spiderweb.request import Request

    req = Request(environ=environ, server=app)

    del req._session

    logout(req)

    assert req.SESSION == {}
    assert not hasattr(req, "user")
    assert not hasattr(req, "_session")
