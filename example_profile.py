from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from spiderweb.main import SpiderwebRouter
from spiderweb.response import TemplateResponse, RedirectResponse
from spiderweb.authentication import login, logout, authenticate
from spiderweb.models import User
from spiderweb.db import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = Column(
        Integer, ForeignKey("spiderweb_users.id"), unique=True
    )
    bio: Mapped[str] = Column(String(500), default="I am a new user.")

    user = relationship("User", backref="profile")


app = SpiderwebRouter(
    middleware=[
        "spiderweb.middleware.sessions.SessionMiddleware",
    ],
)

# Set up DB and test user/profile
db = app.get_db_session()
Base.metadata.create_all(db.get_bind())

if not db.query(User).filter_by(username="testuser").first():
    u = User(username="testuser", email="test@example.com")
    u.set_password("password")
    p = Profile(user=u, bio="Caveman like code. Code good.")
    db.add(u)
    db.add(p)
    db.commit()
db.close()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
    <head>
        <title>Spiderweb Profile Example</title>
    </head>
    <body>
        <h2>Profile Example</h2>
        <p><strong>Status:</strong> {{ status }}</p>
        <p><strong>User:</strong> {{ username }}</p>
        {% if is_auth %}
            <p><strong>Bio:</strong> {{ bio }}</p>
        {% endif %}
        <hr>
        <p>Test credentials:</p>
        <ul>
            <li>Username: <strong>testuser</strong></li>
            <li>Password: <strong>password</strong></li>
        </ul>
        <div>
            {% if not is_auth %}
            <form action="/login" method="POST">
                <input name='username' type='text'>
                <input name='password' type='password'>
                <button type="submit">Log In</button>
            </form>
            {% else %}
            <form action="/logout" method="POST" style="padding-top: 10px">
                <button type="submit">Log Out</button>
            </form>
            {% endif %}
        </div>
    </body>
</html>
"""


@app.route("/", allowed_methods=["GET"])
def index(request):
    is_auth = getattr(request, "user", None) and request.user.is_authenticated
    status = "Logged In" if is_auth else "Not Logged In"
    username = request.user.username if is_auth else "Anonymous"

    bio = ""
    if is_auth:
        db = request.app.get_db_session()
        profile = db.query(Profile).filter_by(user_id=request.user.id).first()
        if profile:
            bio = profile.bio
        db.close()

    return TemplateResponse(
        request,
        template_string=HTML_TEMPLATE,
        context={
            "status": status,
            "username": username,
            "bio": bio,
            "is_auth": is_auth,
        },
    )


@app.route("/login", allowed_methods=["POST"])
def do_login(request):
    user = authenticate(
        request,
        username=request.POST.get("username"),
        password=request.POST.get("password"),
    )
    if user:
        login(request, user)
    return RedirectResponse("/")


@app.route("/logout", allowed_methods=["POST"])
def do_logout(request):
    logout(request)
    return RedirectResponse("/")


if __name__ == "__main__":
    app.start()
