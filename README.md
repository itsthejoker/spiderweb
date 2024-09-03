# spiderweb

<p align="center">
    <img
    src="https://img.shields.io/pypi/v/spiderweb-framework.svg?style=for-the-badge"
    alt="PyPI release version for Spiderweb"
    />
    <img
        src="https://img.shields.io/badge/gitmoji-%20😜%20😍-FFDD67.svg?style=for-the-badge"
        alt="Gitmoji"
    />
    <img 
        src="https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge"
        alt="Code style: Black"
    />
</p>

As a professional web developer focusing on arcane uses of Django for arcane purposes, it occurred to me a little while ago that I didn't actually know how a web framework _worked_.

So I built one.

`spiderweb` is a small web framework, just big enough to hold a spider. Getting started is easy:

```shell
poetry add spiderweb-framework
```

Create a new file and drop this in it:

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

## [View the docs here!](https://itsthejoker.github.io/spiderweb/#/)

My goal with this framework was to do three things:

  1. Learn a lot
  2. Create an unholy blend of Django and Flask
  3. Not look at any existing code. Go off of vibes alone and try to solve all the problems I could think of in my own way

And, honestly, I think I got there. Here's a non-exhaustive list of things this can do:

- Function-based views
- Optional Flask-style URL routing
- Optional Django-style URL routing
- URLs with variables in them a lá Django
- Full middleware implementation
- Limit routes by HTTP verbs
- Custom error routes
- Built-in dev server
- Gunicorn support
- HTML templates with Jinja2
- Static files support
- Cookies (reading and setting)
- Optional append_slash (with automatic redirects!)
- CSRF middleware
- CORS middleware
- Optional POST data validation middleware with Pydantic
- Session middleware with built-in session store
- Database support (using Peewee, but you can use whatever you want as long as there's a Peewee driver for it)
- Tests (currently roughly 89% coverage)
