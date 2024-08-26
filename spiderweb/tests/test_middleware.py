from datetime import timedelta

from peewee import SqliteDatabase

from spiderweb import SpiderwebRouter, HttpResponse
from spiderweb.constants import DEFAULT_ENCODING
from spiderweb.middleware.sessions import Session
from spiderweb.tests.helpers import setup

# app = SpiderwebRouter(
#     middleware=[
#         "spiderweb.middleware.sessions.SessionMiddleware",
#         "spiderweb.middleware.csrf.CSRFMiddleware",
#         "example_middleware.TestMiddleware",
#         "example_middleware.RedirectMiddleware",
#         "spiderweb.middleware.pydantic.PydanticMiddleware",
#         "example_middleware.ExplodingMiddleware",
#     ],
# )

def index(request):
    if "value" in request.SESSION:
        request.SESSION['value'] += 1
    else:
        request.SESSION['value'] = 0
    return HttpResponse(body=str(request.SESSION['value']))


def test_session_middleware():
    _, environ, start_response = setup()
    app = SpiderwebRouter(
        middleware=["spiderweb.middleware.sessions.SessionMiddleware"],
        db=SqliteDatabase("spiderweb-tests.db")
    )

    app.add_route("/", index)

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "1.1.1.1"

    assert app(environ, start_response) == [bytes(str(0), DEFAULT_ENCODING)]

    session_key = Session.select().first().session_key
    environ["HTTP_COOKIE"] = f"swsession={session_key}"

    assert app(environ, start_response) == [bytes(str(1), DEFAULT_ENCODING)]
    assert app(environ, start_response) == [bytes(str(2), DEFAULT_ENCODING)]

def test_expired_session():
    _, environ, start_response = setup()
    app = SpiderwebRouter(
        middleware=["spiderweb.middleware.sessions.SessionMiddleware"],
        db=SqliteDatabase("spiderweb-tests.db")
    )

    app.add_route("/", index)

    environ["HTTP_USER_AGENT"] = "hi"
    environ["REMOTE_ADDR"] = "1.1.1.1"

    assert app(environ, start_response) == [bytes(str(0), DEFAULT_ENCODING)]

    session = Session.select().first()
    session.created_at = session.created_at - timedelta(seconds=app.session_max_age)
    session.save()

    environ["HTTP_COOKIE"] = f"swsession={session.session_key}"

    # it shouldn't increment because we get a new session
    assert app(environ, start_response) == [bytes(str(0), DEFAULT_ENCODING)]

    session2 = list(Session.select())[-1]
    assert session2.session_key != session.session_key


def test_exploding_middleware():
    _, environ, start_response = setup()
    app = SpiderwebRouter(
        middleware=[
            "spiderweb.tests.middleware.ExplodingRequestMiddleware",
            "spiderweb.tests.middleware.ExplodingResponseMiddleware",
        ],
        db=SqliteDatabase("spiderweb-tests.db")
    )

    app.add_route("/", index)

    assert app(environ, start_response) == [bytes(str(0), DEFAULT_ENCODING)]
