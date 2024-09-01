# spiderweb

<p align="center">
    <img
    src="https://img.shields.io/pypi/v/spiderweb-framework.svg?style=for-the-badge"
    alt="PyPI release version for Spiderweb"
    />
    <a href="https://gitmoji.dev">
      <img
        src="https://img.shields.io/badge/gitmoji-%20😜%20😍-FFDD67.svg?style=for-the-badge"
        alt="Gitmoji"
      />
    </a>
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

My goal with this framework was to do three things:

  1. Learn a lot
  2. Create an unholy blend of Django and Flask
  3. Not look at any existing code. Go off of vibes alone and try to solve all the problems I could think of in my own way

And, honestly, I think I got there. Here's a non-exhaustive list of things this can do:

  * Function-based views
  * Optional Flask-style URL routing
  * Optional Django-style URL routing
  * URLs with variables in them a lá Django
  * Gunicorn support
  * Full middleware implementation
  * Limit routes by HTTP verbs
  * Custom error routes
  * Built-in dev server
  * HTML templates with Jinja2
  * Static files support
  * Cookies (reading and setting)
  * Optional append_slash (with automatic redirects!)
  * ~~CSRF middleware implementation~~ (it's there, but it's crappy and unsafe. I'm working on it.)
  * Optional POST data validation middleware with Pydantic
  * Database support (using Peewee, but the end user can use whatever they want as long as there's a Peewee driver for it)
  * Session middleware

The TODO list:

  * Tests (important)
  * Fix CSRF middleware

Once tests are in and proven to work, then I'll release as version 1.0.

More documentation to follow!

If you're reading this on GitHub, this repository is a public mirror of https://git.joekaufeld.com/jkaufeld/spiderweb.