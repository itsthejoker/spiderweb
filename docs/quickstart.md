# quickstart

Start by installing the package with your favorite package manager:

<!-- tabs:start -->

<!-- tab:poetry -->

```shell
poetry add spiderweb-framework
```

<!-- tab:pip -->

```shell
pip install spiderweb-framework
```

<!-- tab:pipenv -->

```shell
pipenv install spiderweb-framework
```

<!-- tabs:end -->

Then, create a new file and drop this in it:

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse

app = SpiderwebRouter()

@app.route("/")
def index(request):
    return HttpResponse("HELLO, WORLD!")

if __name__ == "__main__":
    app.start()
```

Start the dev server by running `python {yourfile.py}` and navigating to `http://localhost:8000/` in your browser. You should see `HELLO, WORLD!` displayed on the page. Press `Ctrl+C` to stop the server.

That's it! You've got a working web app. Let's take a look at what these few lines of code are doing:

```python
from spiderweb import SpiderwebRouter
```

The `SpiderwebRouter` class is the main object that everything stems from in Spiderweb. It's where you'll set your options, your routes, and more.

```python
from spiderweb.response import HttpResponse
```

Rather than trying to infer what you want, Spiderweb wants you to be specific about what you want it to do. Part of that is the One Response Rule:

> Every view must return a Response, and each Response must be a specific type.

There are five different types of responses; if you want to skip ahead, hop over to [the responses page](responses.md) to learn more. For this example, we'll focus on `HttpResponse`, which is the base response.

```python
app = SpiderwebRouter()
```

This line creates a new instance of the `SpiderwebRouter` class and assigns it to the variable `app`. This is the object that will handle all of your requests and responses. If you need to pass any options into Spiderweb, you'll do that here.

```python
@app.route("/")
def index(request):
    return HttpResponse("HELLO, WORLD!")
```

This is an example view. There are a few things to note here:

- The `@app.route("/")` decorator tells spiderweb that this view should be called when the user navigates to the root of the site. There are three different ways to declare this, but this is the easiest for demo purposes.
- The `def index(request):` function is the view itself. It takes a single argument, `request`, which is a `Request` object that contains all the information about the incoming request.
- The `return HttpResponse("HELLO, WORLD!")` line is the response. In this case, it's a simple `HttpResponse` object that contains the string `HELLO, WORLD!`. This will be sent back to the user's browser.

> See [declaring routes](routes.md) for more information.

> [!NOTE]
> Every view must accept a `request` object as its first argument. This object contains all the information about the incoming request, including headers, cookies, and more.
> 
> There's more that we can pass in, but for now, we'll keep it simple.

```python
if __name__ == "__main__":
    app.start()
```

Once you finish setting up your app, it's time to start it! You can start the dev server by just calling `app.start()` (and its counterpart `app.stop()`, or just CTRL+C). This will start a simple server on `localhost:8000` that you can access in your browser.

> [!WARNING]
> The dev server is just that: for development. Do not use for production.

Now that your app is done, you can also run it with Gunicorn by running `gunicorn --workers=2 {yourfile}:app` in your terminal. This will start a Gunicorn server on `localhost:8000` that you can access in your browser and is a bit more robust than the dev server.
