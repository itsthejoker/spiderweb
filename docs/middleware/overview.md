# middleware

When processing a request, there are often things that need to happen before the request is passed to the view. Middleware is a way to intercept the request and response objects and do something with them before they are passed to the view or returned to the client.

Middleware in Spiderweb is defined as a list of importable strings that looks like this:

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    middleware=[
            "spiderweb.middleware.sessions.SessionMiddleware",
            "spiderweb.middleware.csrf.CSRFMiddleware",
            "spiderweb.middleware.pydantic.PydanticMiddleware",
        ],
)
```

Middleware affects both the incoming request AND the outgoing response, so the order that it's defined here is important. When a request comes in, it will be processed through the middleware in the order that it's defined, but after the response is created, it will pass back through the middleware going the opposite direction. 