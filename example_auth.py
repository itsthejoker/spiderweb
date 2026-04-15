from spiderweb.main import SpiderwebRouter
from spiderweb.response import HttpResponse, RedirectResponse, TemplateResponse
from spiderweb.authentication import login, logout, authenticate
from spiderweb.models import User

app = SpiderwebRouter(
    middleware=[
        "spiderweb.middleware.sessions.SessionMiddleware",
    ],
)

# Set up a test user in the database
db = app.get_db_session()
if not db.query(User).filter_by(username="testuser").first():
    u = User(username="testuser", email="test@example.com")
    u.set_password("password")
    db.add(u)
    db.commit()
db.close()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
    <head>
        <title>Spiderweb Auth!</title>
    </head>
    <body>
        <h2>Authentication Example</h2>
        <p><strong>Status:</strong> {{ status }}</p>
        <p><strong>User:</strong> {{ username }}</p>
        <hr>
        <p>Test credentials:</p>
        <ul>
            <li>Username: <strong>testuser</strong></li>
            <li>Password: <strong>password</strong</li>
        </ul>
        <div>
            <form action="/login" method="POST">
                <input name='username' type='text'>
                <input name='password' type='password'>
                <button type="submit">Log In</button>
            </form>
            <form action="/logout" method="POST" style="padding-top: 10px">
                <button type="submit">Log Out</button>
            </form>
        </div>
    </body>
</html>
"""


@app.route("/", allowed_methods=["GET"])
def index(request):
    is_auth = getattr(request, "user", None) and request.user.is_authenticated
    status = "Logged In" if is_auth else "Not Logged In"
    username = request.user.username if is_auth else "Anonymous"

    return TemplateResponse(
        request, template_string=HTML_TEMPLATE, context={'status': status, 'username': username}
    )


@app.route("/login", allowed_methods=["POST"])
def do_login(request):
    user = authenticate(
        request,
        username=request.POST.get('username'),
        password=request.POST.get('password')
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
