# handling file uploads

> New in 2.2.0!

Spiderweb supports handling file uploads via standard HTML forms that use multipart/form-data. Uploaded files are parsed into Request.FILES as a MultiDict of MediaFile objects, which provide convenient helpers like filename, content_type, size, read(), seek(), and save().

> [!TIP]
> If you're just getting started, try the working example in example.py together with templates/file_upload.html in this repository.

## Configuration: where to store uploads

When you intend to save uploaded files to disk during development, point Spiderweb at a media directory. In debug mode, Spiderweb will also register a development-only route to serve files back from that folder.

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    media_dir="media",     # folder relative to your app file
    media_url="media",     # URL prefix used to serve media in debug
    debug=True,             # required for dev-time file serving
)
```

- If media_dir does not exist, it is created on startup.
- In debug=True, requests to /{media_url}/<path:filename> are served from the media_dir folder.

> [!DANGER]
> Serving uploaded files directly from your app is for local development only. In production, serve uploads via a reverse proxy (nginx/Apache) or an object store (S3, GCS) and protect access appropriately.

## HTML forms: enctype is required

To send a file from the browser, your form must:

- use method="post"
- include enctype="multipart/form-data"
- include one or more <input type="file" name="..."> controls

```html
<form action="" method="post" enctype="multipart/form-data">
  <input name="file" type="file">
  {{ csrf_token }}
  <button type="submit">Upload</button>
</form>
```

> [!NOTE]
> The {{ csrf_token }} comes from the CSRF middleware and should be included in POST forms. See Middleware → CSRF for details.

## Accessing uploaded files in a view

Uploaded files are available as MediaFile objects in request.FILES. The key matches the input name attribute.

```python
from spiderweb.response import HttpResponse, TemplateResponse

@app.route("/upload", allowed_methods=["GET", "POST"])
def upload(request):
    if request.method == "POST":
        if "file" not in request.FILES:
            return HttpResponse("No file uploaded", status_code=400)
        file: MediaFile = request.FILES["file"]

        # Inspect metadata
        name = file.filename          # original filename
        mime = file.content_type      # e.g., "text/plain" or "image/png"
        size = file.size              # in bytes

        # Option A: read content (for validation or quick processing)
        content_bytes = file.read()
        # If you plan to call save() after reading, rewind first:
        file.seek(0)

        # Option B: save to disk (returns full path)
        saved_path = file.save()
        return HttpResponse(f"Saved {name} to {saved_path}", status_code=201)

    # GET → render the form
    return TemplateResponse(request, "file_upload.html")
```

### What does MediaFile.save() do?

- Writes the uploaded content to BASE_DIR / media_dir / filename.
- If a file with the same name already exists, a short random suffix is appended before the extension, e.g., photo_[AbCdEf].png.
- Returns a pathlib.Path to the saved file.

### Multiple files with the same name

If the file input uses multiple, the browser submits several parts with the same name. Use request.FILES.getall(name) to retrieve all of them.

```python
files = request.FILES.getall("photos")
for f in files:
    f.save()
```

And the corresponding HTML:

```html
<input name="photos" type="file" multiple>
```

## Serving uploaded files in development

With debug=True and media_dir set, Spiderweb automatically registers a development route so you can access uploaded files at:

- /{media_url}/<filename>

Example: with media_dir="media" and media_url="media", a saved file named avatar.png will be accessible at /media/avatar.png while debug is true.

> [!DANGER]
> Do not rely on the development file server in production. Put your web server or CDN in front of your app to serve media safely and efficiently.

## CSRF and uploads

Uploads are POST requests and are protected by the CSRF middleware. To accept submissions:

- Add SessionMiddleware before CSRFMiddleware in your app config.
- Include {{ csrf_token }} in your form markup.

See [CSRF middleware](middleware/csrf.md) for a complete example.

## Validation and security tips

- Validate file type and size before accepting. Do not trust filename extensions alone; inspect content_type and/or file signatures when it matters.
- Store files outside your templates directories. Use media_dir for user content.
- Normalize user-supplied metadata before storing in your database.
- Consider scanning uploads (e.g., antivirus) if you accept untrusted files.

## Complete minimal example

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse, TemplateResponse

app = SpiderwebRouter(
    templates_dirs=["templates"],
    middleware=[
        "spiderweb.middleware.sessions.SessionMiddleware",
        "spiderweb.middleware.csrf.CSRFMiddleware",
    ],
    media_dir="media",
    media_url="media",
    debug=True,
)

@app.route("/upload", allowed_methods=["GET", "POST"])
def upload(request):
    if request.method == "POST":
        if "file" not in request.FILES:
            return HttpResponse("No file uploaded", status_code=400)
        file = request.FILES["file"]
        # Save and echo the location
        saved = file.save()
        return HttpResponse(f"Uploaded to {saved}", status_code=201)
    return TemplateResponse(request, "file_upload.html")
```

```html
<!-- templates/file_upload.html -->
<form action="" method="post" enctype="multipart/form-data">
  <input name="file" type="file">
  {{ csrf_token }}
  <button type="submit">Upload</button>
</form>
```
