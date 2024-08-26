# spiderweb

As a professional web developer focusing on arcane uses of Django for arcane purposes, it occurred to me a little while ago that I didn't actually know how a web framework _worked_.

> So I built one.

This is `spiderweb`, a WSGI-compatible web framework that's just big enough to hold a spider. When building it, my goals were simple:

- Learn a lot
- Create an unholy blend of Django and Flask
- Not look at any existing code. Go off of vibes alone and try to solve all the problems I could think of in my own way

> [!WARNING]
> This is a learning project. It should not be used for production without heavy auditing. It's not secure. It's not fast. It's not well-tested. It's not well-documented. It's not well-anything. It's a learning project.
> 
> That being said, it's fun and it works, so I'm counting that as a win.


## Design & Usage Decisions

There are a couple of things that I feel strongly about that have been implemented into Spiderweb.

### Deliberate Responses

In smaller frameworks, it's often the case that "how to return the response" is guessed based on the data that you return from a view. Take this view for example:

```python
def index(request):
    return "Hi"
```

In this function, we return a string, and as such there are some assumptions that we make about what the response looks like:

- a content-type header of "text/plain"
- that we are wanting to return raw HTML
- no post-processing of the response is needed

While assumptions are nice for getting running quickly, I think that there is a balance between assuming what the user wants and making them define everything. See how Spiderweb handles this:

```python
from spiderweb.response import HttpResponse

def index(request):
    return HttpResponse("Hi")
```

In this case, we improve readability of exactly what type of response we expect (raw HTML, a template response, a JSON-based response, etc.) and we give the developer the tools that they need to modify the response beforehand.

The response object has everything that it needs immediately available: headers, cookies, status codes, and more. All can be modified before sending, but providing this data for the opportunity to change is what's important.

Spiderweb provides five types of responses out of the box:

- HttpResponse
- FileResponse
- RedirectResponse
- TemplateResponse
- JSONResponse

> [Read more about responses in Spiderweb](responses.md)

### Database Agnosticism (Mostly)

One of the largest selling points of Django is the Django Object Relational Mapper (ORM); while there's nothing that compares to it in functionality, there are many other ORMs and database management solutions for developers to choose from.

In order to use a database internally (and since this is not about writing an ORM too), Spiderweb depends on [peewee, a small ORM](https://github.com/coleifer/peewee). Applications using Spiderweb are more than welcome to use peewee models with first-class support or use whatever they're familiar with. Peewee supports PostgreSQL, MySQL, Sqlite, and CockroachDB; if you use one of these, Spiderweb can create the tables it needs in your database and stay out of the way. By default, Spiderweb creates a sqlite database in the application directory for its own use.

> [Read more about the using a database in Spiderweb](db.md)

### Easy to configure

Configuration is handled in different ways across different frameworks; in Flask, a simple dictionary is used that you can modify:

```python
# https://flask.palletsprojects.com/en/3.0.x/config/
app = Flask(__name__)
app.config['TESTING'] = True
```

This works, but suffers from the problem of your IDE not being able to see all the possible options that are available. Django solves this by having a `settings.py` file:

```python
# https://docs.djangoproject.com/en/5.1/topics/settings/
ALLOWED_HOSTS = ["www.example.com"]
DEBUG = False
DEFAULT_FROM_EMAIL = "webmaster@example.com"
```

Simply having these declared in a place that Django can find them is enough, and they Just Work:tm:. This also works, but can be very verbose.

Spiderweb takes a middle ground approach: it allows you to declare framework-first arguments on the SpiderwebRouter object, and if you need to pass along other data to other parts of the system (like custom middleware), you can do so by passing in any keyword argument you'd like to the constructor.

```python
from peewee import SqliteDatabase

app = SpiderwebRouter(
  db=SqliteDatabase("myapp.db"),
  port=4500,
  session_cookie_name="myappsession",
  my_middleware_data="Test!"
)
```

In this example, `db`, `port`, and `session_cookie_name` are all arguments that affect the server, but `my_middleware_data` is something new. It will be available in `app.extra_data` and is also available through middleware and on the request object later.

## tl;dr: what can Spiderweb do?

Here's a non-exhaustive list of things this can do:

- Function-based views
- Optional Flask-style URL routing
- Optional Django-style URL routing
- URLs with variables in them a lá Django
- Full middleware implementation
- Limit routes by HTTP verbs
  - (Only GET and POST are implemented right now)
- Custom error routes
- Built-in dev server
- Gunicorn support
- HTML templates with Jinja2
- Static files support
- Cookies (reading and setting)
- Optional append_slash (with automatic redirects!)
- ~~CSRF middleware implementation~~ (it's there, but it's crappy and unsafe. This might be beyond my skillset.)
- Optional POST data validation middleware with Pydantic
- Database support (using Peewee, but you can use whatever you want as long as there's a Peewee driver for it)
- Session middleware with built-in session store
- Tests (currently a little over 80% coverage)

## What's left to build?

- Fix CSRF middleware
- Add more HTTP verbs
