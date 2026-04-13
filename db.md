# databases

Spiderweb is intentionally ORM-agnostic. Internally, it now uses Advanced Alchemy (built on SQLAlchemy) to persist first‑party data like sessions. You can choose one of the following approaches for your application data:

- Option 1: Use the built‑in Advanced Alchemy/SQLAlchemy setup
- Option 2: Bring your own ORM and manage its lifecycle
- Option 3: Use separate databases for Spiderweb internals and your app data

## Option 1: Use the built‑in Advanced Alchemy/SQLAlchemy setup

By default, Spiderweb will create and use a SQLite database file named `spiderweb.db` in your application directory. You can change this by passing the `db` argument to `SpiderwebRouter` as any of the following:

- A SQLAlchemy Engine instance
- A database URL string (e.g., `sqlite:///path/to.db`, `postgresql+psycopg://user:pass@host/db`)
- A filesystem path string for SQLite (e.g., `my_db.sqlite`)

Examples:

```python
from sqlalchemy import create_engine
from spiderweb import SpiderwebRouter

# Use a SQLite file by passing a path
app = SpiderwebRouter(db="my_db.sqlite")

# Or pass a SQLAlchemy engine
engine = create_engine("postgresql+psycopg://user:pass@localhost/myapp")
app = SpiderwebRouter(db=engine)

# Or pass a full URL string
app = SpiderwebRouter(db="sqlite:///./local.db")
```

## Option 2: Bring your own ORM

If you are using another ORM or data layer, create and manage it as you normally would. If you need per‑request access to a connection or session, you can attach it via custom middleware:

```python
from spiderweb.middleware import SpiderwebMiddleware
from sqlalchemy import create_engine


class SQLAlchemyMiddleware(SpiderwebMiddleware):
    engine = None

    def process_request(self, request) -> None:
        if not self.engine:
            self.engine = create_engine("sqlite:///spiderweb.db")
        request.engine = self.engine
```

Now any view that receives the incoming request object can access `request.engine` and interact with the database as needed.

> See [Writing Your Own Middleware](middleware/custom_middleware.md) for more information.

## Option 3: Use two databases

If your application requires a database not supported by SQLAlchemy or you prefer to keep concerns separated, you can run two databases: one for Spiderweb internals (sessions, etc.) and one for your application logic.

## Migrations

Advanced Alchemy works seamlessly with Alembic (SQLAlchemy's migration tool). To manage schema changes:

1. Install Alembic:

   ```bash
   pip install alembic
   ```

2. Initialize a migration repository:

   ```bash
   alembic init migrations
   ```

3. Configure Alembic to use Spiderweb's metadata. In `migrations/env.py`, set:

   ```python
   from spiderweb.db import Base
   target_metadata = Base.metadata
   ```

   Also set the database URL either in `alembic.ini` (`sqlalchemy.url = ...`) or dynamically in `env.py` (read from environment variables or config).

4. Generate migrations from model changes:

   ```bash
   alembic revision --autogenerate -m "add my table"
   ```

5. Apply migrations:

   ```bash
   alembic upgrade head
   ```

Notes:
- If you define your own SQLAlchemy models, make sure they inherit from `spiderweb.db.Base` (or include their metadata in `target_metadata`) so Alembic can discover them.
- For multi-database setups, you can configure multiple Alembic contexts or run Alembic separately per database.
- Advanced Alchemy provides additional helpers on top of SQLAlchemy; you can use them freely alongside the guidance above.
