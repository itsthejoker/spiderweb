from spiderweb.main import SpiderwebRouter
from spiderweb.response import HttpResponse
from spiderweb.routes import View

app = SpiderwebRouter(debug=True)


# The decorator system works along with everything else!
@app.route("/")
class Index(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse("This is a GET request from a class!")


# app.add_route("/", Index)

if __name__ == "__main__":
    app.start()
