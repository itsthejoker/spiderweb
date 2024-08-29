# sessions middleware

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    middleware=["spiderweb.middleware.sessions.SessionMiddleware"],
)
```

Arguably one of the more important things that a server-side web framework can do, besides take in requests and serve responses, is keep track of folks as they navigate your website. That's what the sessions middleware is for!

Visitors are assigned a random value when they visit for the first time, and that value will follow them around until it either expires or it's deleted. The total amount of time that it's around is configurable, as are the various settings for the session cookie.

## request.SESSION

When the sessions middleware is enabled, the request object will have a new attribute labeled `SESSION`. This is a dictionary, and you can put pretty much anything you want in it as long as it's serializable to JSON! When the user visits again with an active session, the data will automatically be available on the `SESSION` object again. Here's an example of a complete server using sessions:

```python
from spiderweb import SpiderwebRouter, HttpResponse

app = SpiderwebRouter(
    middleware=["spiderweb.middleware.sessions.SessionMiddleware"],
)

@app.route("/")
def session(request):
    if "val" not in request.SESSION:
        request.SESSION["val"] = 0
    else:
        request.SESSION["val"] += 1
    return HttpResponse(body=f"Session value: {request.SESSION['val']}")

if __name__ == "__main__":
    app.start()
```

If you drop this into a new file and call it with `python yourfile.py`, you should see two things:

- there is a new file created called `spiderweb.db`
- if you open your browser and navigate to http://localhost:8000 and refresh the page a few times, the number should increment

Use the session object to keep track of anything you need to!

> Read more [about the database here!](../db.md)

## Settings

There are a few configurable things with the settings middleware, and they all have to do with the cookie itself.

```python
app = SpiderwebRouter(
    session_cookie_name="swsession",
    session_cookie_secure=False,
    session_cookie_http_only=True,
    session_cookie_same_site="lax",
    session_cookie_path="/",
)
```

### session_cookie_name

Any valid cookie name is acceptable here; the default is `swsession`. You can [read more about valid names for cookies here][cookienames].

### session_cookie_secure

This marks that the cookie will only be sent back to the server with a valid HTTPS session. By default, this is set to `False`, but should be manually set to `True` if the server is deployed.

### session_cookie_http_only

This marks whether the session cookie will have the `HttpOnly` attribute. This makes it unreadable to client-side javascript. The default is `False`.

### session_cookie_same_site

There are three valid values for this: "strict", "lax", and "none".

- `strict`: the browser will only send the cookie when the user performs a request on the same site that sent the cookie, and notably not on the first request to the server when navigating to the site from a different origin.
- `lax`: the browser will send the cookie when the user performs a request on the same site that sent the cookie, and also on the first request to the server when navigating to the site from a different origin. This is the default setting.
- `none`: the browser will send the cookie regardless of the origin of the request. However, you must also set `session_cookie_secure` to `True` if you want to use this setting, otherwise the browser will refuse to send it.

### session_cookie_path

This is the path that the cookie is valid for. By default, it's set to `/`, which means that the cookie is valid for the entire domain. If you want to restrict the cookie to a specific path, you can set it here.

[cookienames]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie#attributes
