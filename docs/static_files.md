# serving static files for local development

When you're developing locally, it's often useful to be able to serve static files directly from your application, especially when you're working on the frontend. Spiderweb does have a mechanism for serving static files, but it's _not recommended_ (read: this is a Very Bad Idea) for production use. Instead, you should use a reverse proxy like nginx or Apache to serve them.

To serve static files locally, you'll need to tell Spiderweb where they are. Once you fill this out, Spiderweb will automatically handle the routing to find them.

Before we get started:

> [!DANGER]
> Having Spiderweb handle your static files in production is a **critical safety issue**. It does its best to identify if a request is malicious, but it is much safer to have this be handled by a reverse proxy.

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    staticfiles_dirs=[
        "my_static_files", 
        "maybe_other_static_files_here"
    ],
    debug=True,
    static_url="assets",
)
```

> [!NOTE]
> Note the `debug` attribute in the example above; even if `staticfiles_dirs` is set, Spiderweb will only serve the files if `debug` is set to `True`. This is a safety check for you and an easy toggle for deployment.

## `staticfiles_dirs`

> default: `[]`

This is a list of directories that Spiderweb will look in for static files. When a request comes in for a static file, Spiderweb will look in each of these directories in order to find the file. If it doesn't find the file in any of the directories, it will return a 404.

## `static_url`

> default: `static`

This is the URL that Spiderweb will use to serve static files. In the example above, the URL would be `http://localhost:8000/assets/`. If you don't set this, Spiderweb will default to `/static/`.

## `debug`

> New in 1.2.0!

> default: `False`

This is a boolean that tells Spiderweb whether it is running in debug mode or not. Among other things, it's used in serving static files. If this value is not included, it defaults to False, and Spiderweb will not serve static files. For local development, you will want to set it to True.

## Linking to static files

> New in 1.2.0!

There is a tag in the templates that you can use to link to static files. This tag will automatically generate the correct URL for the file based on the `static_url` attribute you set in the router.

```html
<img 
    src="{% static 'hello_world.gif' %}" 
    alt="A rotating globe with the caption, 'hello world'."
>
```

In this example, the `static` tag will generate a URL that looks like `/assets/hello_world.gif`. This is the URL that the browser will use to request the file. If you have a file that is in a folder, you can specify that in the tag:

```html
<img 
    src="{% static 'gifs/landing/hello_world.gif' %}" 
    alt="A rotating globe with the caption, 'hello world'."
>
```
This will pull the gif from `{your static folder}/gifs/landing/hello_world.gif`.
