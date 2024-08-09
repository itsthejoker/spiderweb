from spiderweb import WebServer
from spiderweb.response import HttpResponse, JsonResponse, TemplateResponse, RedirectResponse


app = WebServer(
    templates_dirs=["templates"],
    middleware=[
        "example_middleware.TestMiddleware",
        "example_middleware.RedirectMiddleware",
        "example_middleware.ExplodingMiddleware",
    ],
    append_slash=False  # default
)


@app.route("/")
def index(request):
    return TemplateResponse(request, "test.html", context={"value": "TEST!"})


@app.route("/redirect")
def redirect(request):
    return RedirectResponse("/")


@app.route("/json")
def json(request):
    return JsonResponse(data={"key": "value"})


@app.route("/error")
def error(request):
    return HttpResponse(status_code=500, body="Internal Server Error")


@app.route("/middleware")
def middleware(request):
    return HttpResponse(
        body="We'll never hit this because it's redirected in middleware"
    )


@app.route("/example/<int:id>")
def example(request, id):
    return HttpResponse(body=f"Example with id {id}")


if __name__ == "__main__":
    # can also add routes like this:
    # app.add_route("/", index)
    app.start()
