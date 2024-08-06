from spiderweb import WebServer
from spiderweb.response import HttpResponse, JsonResponse, TemplateResponse, RedirectResponse

app = WebServer(templates_dirs=["templates"])


@app.route("/")
def index(request):
    return TemplateResponse(request, "test.html", context={"value": "TEST!"})


@app.route("/redirect")
def redirect(request):
    return RedirectResponse("/")


if __name__ == "__main__":
    # app.add_route("/", index)
    try:
        app.start()
        print("Currently serving on", app.uri())
    except KeyboardInterrupt:
        app.stop()
