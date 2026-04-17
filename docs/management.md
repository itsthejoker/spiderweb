---
icon: command-palette
nav:
  badge: NEW|info
order: 850
---

# management

[!badge New in 2.4.0!]

Spiderweb ships with a built-in management CLI — a single command you can use to start the dev server, explore your routes, open an interactive shell, and run startup checks. If you've ever used Django's `manage.py`, this will feel familiar.

After installing the package, the `web` command is available in your environment:

```shell
web --help
```

## pointing the CLI at your app

All commands (except `version`) need to know which `SpiderwebRouter` instance to work with. There are three ways to tell them, in order of priority:

**1. The `--app` flag**

Pass the app location directly on the command line as `module:attribute`:

```shell
web --app myapp:app serve
```

**2. The `SPIDERWEB_APP` environment variable**

This is helpful for CI pipelines of for folks who like to have everything set in the shell.

```shell
export SPIDERWEB_APP=myapp:app
web serve
```

**3. `pyproject.toml`**

Add a `[tool.spiderweb]` section to your project's `pyproject.toml`. The CLI walks up from your current directory until it finds one:

```toml
[tool.spiderweb]
app = "myapp:app"
```

With that in place you can use any command bare, with no flags at all:

```shell
web serve
```

> [!TIP]
> The `pyproject.toml` approach is the most ergonomic for day-to-day development. Set it once and forget about it.

## commands

### version

Prints the installed version of `spiderweb`.

```shell
$ web version
spiderweb-framework 2.4.0
```

### new

Scaffolds a new Spiderweb project. It creates a new directory containing a minimal `app.py` and a `pyproject.toml` configured for your app. Like `version`, this command doesn't need an app to run.

```shell
$ web new my_project
```

You can also scaffold into the current directory by passing `.`:

```shell
$ web new .
```

If the target directory already has a `pyproject.toml`, it will append the `[tool.spiderweb]` section without overwriting your existing config.

### serve

Starts the development server. By default it runs in WSGI mode on whatever address and port your app was configured with (`localhost:8000` unless you changed them).

```shell
web serve
```

Switch to ASGI mode with `--asgi`:

```shell
web serve --asgi
```

Override the bind address or port without touching your source code:

```shell
web serve --addr 0.0.0.0 --port 9000
```

If your project always runs in ASGI mode, set `asgi = true` in `[tool.spiderweb]`:

```toml
[tool.spiderweb]
app = "myapp:app"
asgi = true
```

You can still override it on the command line in either direction — `--asgi` forces ASGI, `--wsgi` forces WSGI regardless of what `pyproject.toml` says.

> [!WARNING]
> The dev server is just that: for development. Do not use for production.

### shell

Opens an interactive Python interpreter with your app already loaded as `app`. Great for poking around at runtime state, testing a database query, or trying out a piece of logic before committing it.

```shell
$ web shell
Spiderweb 2.4.0 shell
Available names: app
Type "exit()" or Ctrl-D to quit.

>>> app.addr
'localhost'
>>> with app.get_db_session() as session:
...     # query away
...     pass
```

If [IPython](https://ipython.org/) is installed in your environment, the shell will use it automatically. Otherwise, it falls back to the standard library `code.interact`.

### routes

Prints a table of every URL route your app has registered — path, allowed methods, optional name, and the view function.

```shell
$ web routes
path            methods                              name   view
-----------------------------------------------------------------------
/               POST, GET, PUT, PATCH, DELETE               index
/about          POST, GET, PUT, PATCH, DELETE               about
/posts/{slug}   POST, GET, PUT, PATCH, DELETE        posts  get_post
```

Routes that haven't restricted their methods show the full default set. If you pass `allowed_methods=["GET"]` to `@app.route()`, only that method appears in the table. Handy for double-checking that a new route was picked up correctly, or for tracking down a duplicate.

### check

Re-runs all middleware startup checks and tells you whether everything looks healthy.

```shell
$ web check
System check passed.
```

If any check fails, a `StartupErrors` exception group is raised — you'll see a one-frame traceback listing every failing check. Useful in CI or as a quick sanity check after a config change.

### makemigrations

Generates a new Alembic migration by comparing your current models against the database schema.

```shell
web makemigrations
web makemigrations -m "add users table"
```

The first time you run this command the CLI scaffolds a `migrations/` directory next to your `pyproject.toml` (or in the current directory if no `pyproject.toml` is found):

```
migrations/
    env.py           ← configure your model metadata here
    script.py.mako   ← template for generated migration files
    versions/        ← individual migration scripts live here
```

By default, Alembic compares spiderweb's own internal tables against the live database. To include your own models, open `migrations/env.py` and add your `Base` to `target_metadata`:

```python
from myapp.models import Base as _AppBase

target_metadata = [_SpiderwebBase.metadata, _AppBase.metadata]
```

**Options**

| Flag | Description |
|---|---|
| `-m MESSAGE` / `--message MESSAGE` | Short description embedded in the migration filename. |
| `--empty` | Create a blank migration without running autogenerate. Useful for hand-written data migrations. |

### migrate

Applies pending migrations to the database. Without arguments it upgrades to the latest revision (`head`).

```shell
web migrate
```

Pass a specific revision ID, a relative step, or the special value `zero` to target a particular point in the migration history:

```shell
web migrate abc123de          # upgrade (or already at this rev: no-op)
web migrate +1                # apply the next pending migration
web migrate -1                # roll back the most recent migration
web migrate zero              # roll back every migration (equivalent to `base`)
```

**Options**

| Flag | Description |
|---|---|
| `REVISION` | Target revision (default: `head`). |
| `--fake` | Stamp the database at the target revision without executing any SQL — useful for marking existing schemas as migrated. |

> [!TIP]
> You can configure where the migrations directory lives by setting `migrations_dir` in `[tool.spiderweb]`:
>
> ```toml
> [tool.spiderweb]
> app = "myapp:app"
> migrations_dir = "db/migrations"
> ```

## custom commands

You can register your own management commands on the router using the `@app.command()` decorator. Every custom command receives three arguments:

- `app` — the `SpiderwebRouter` instance, so you can access the database, routes, config, etc.
- `args` — an `argparse.Namespace` containing only `.app` and `.command` (the values the CLI's own pre-parser resolved). It does **not** contain any flags you pass after the command name.
- `extra` — a plain `list[str]` of every token that appeared after the command name on the command line. Parse this yourself if your command accepts flags.

A command with no extra flags:

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse

app = SpiderwebRouter()

@app.route("/")
def index(request):
    return HttpResponse("hello!")

@app.command("seed")
def seed_database(app, args, extra):
    """Populate the database with initial data."""
    with app.get_db_session() as session:
        # ... insert seed records ...
        session.commit()
    print("Database seeded.")

if __name__ == "__main__":
    app.start()
```

A command that accepts its own flags — parse `extra` with argparse:

```python
import argparse

@app.command("seed")
def seed_database(app, args, extra):
    p = argparse.ArgumentParser(prog="spiderweb seed")
    p.add_argument("--dry-run", action="store_true")
    opts = p.parse_args(extra)

    if opts.dry_run:
        print("Dry run — no changes written.")
        return

    with app.get_db_session() as session:
        session.commit()
    print("Database seeded.")
```

```shell
web seed --dry-run
```

Run any custom command the same way as a built-in:

```shell
web --app myapp:app seed
```

Or, with `pyproject.toml` configured, just:

```shell
web seed
```

> [!NOTE]
> The decorated function is still a regular Python function. Applying `@app.command()` doesn't change it in any way — you can still call it directly in your own code.

You can register as many custom commands as you like. Pick meaningful names; they'll show up in the error message if someone types an unrecognised command, so short and descriptive is best.

## configuration reference

| Option | Description |
|---|---|
| `--app MODULE:ATTR` | The app to use, in `module:attribute` form. Overrides `SPIDERWEB_APP` and `pyproject.toml`. |
| `SPIDERWEB_APP` | Environment variable. Overrides `pyproject.toml`, overridden by `--app`. |
| `[tool.spiderweb] app` | `pyproject.toml` key. Lowest priority; used when neither of the above is set. |
| `[tool.spiderweb] asgi` | `pyproject.toml` boolean. When `true`, `serve` defaults to ASGI mode. Overridden by `--asgi` / `--wsgi`. |
| `[tool.spiderweb] migrations_dir` | Path to the Alembic migrations directory, relative to `pyproject.toml`. Defaults to `migrations`. |

### `serve` options

| Flag | Description |
|---|---|
| `--asgi` | Start in ASGI mode via uvicorn instead of WSGI. |
| `--wsgi` | Force WSGI mode even when `asgi = true` is set in `pyproject.toml`. |
| `--addr ADDR` | Bind address. Overrides the value stored in the app. |
| `--port PORT` | Port number. Overrides the value stored in the app. |

### `makemigrations` options

| Flag | Description |
|---|---|
| `-m MESSAGE` / `--message MESSAGE` | Short description for the migration. |
| `--empty` | Create a blank migration without autogenerate. |

### `migrate` options

| Flag | Description |
|---|---|
| `REVISION` | Target revision (default: `head`). Accepts revision IDs, `+N`/`-N` relative specs, `zero`, or `base`. |
| `--fake` | Stamp the database at the target revision without running SQL. |
