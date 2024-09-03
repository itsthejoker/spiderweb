# databases

It's hard to find a server-side app without a database these days, and for good reason: there are a lot of things to keep track of. Spiderweb does its best to remain database-agnostic, though it does utilize `peewee` internally to handle its own data (such as session data). This means that you have three options for how to handle databases in your app.

## Option 1: Using Peewee

If you'd just like to use the same system that's already in place, you can import `SpiderwebModel` and get to work writing your own models for Peewee. See below for notes on writing your own database models and fitting them into the server and for changing the driver to a different type of database.


## Option 2: Using your own database ORM

You may not want to use Peewee, and that's totally fine; in that case, you will want to tell Spiderweb where the database is so that it can create the tables that it needs. To do this, you'll need to be be using a database type that Peewee supports; at this time, the options are SQLite, MySQL, MariaDB, and Postgres.

You'll want to instantiate your own ORM in the way that works best for you and let Spiderweb know where to find the database. See "Changing the Peewee Database Target" below for information on how to adjust where Spiderweb places data.

Instantiating your own ORM depends on whether your ORM can maintain an application-wide connection or if it needs a new connection on a per-request basis. For example, SQLAlchemy prefers that you use an `engine` to access the database. Since it's not clear at any given point which view will be receiving a request, this might be a good reason for some custom middleware to add an `engine` attribute onto the request that can be retrieved later:

```python
from spiderweb.middleware import SpiderwebMiddleware
from sqlalchemy import create_engine


class SQLAlchemyMiddleware(SpiderwebMiddleware):
    # there's only one of these, so we can just make it a top-level attr
    engine = None
    
    def process_request(self, request) -> None:
        # provide handles for the default `spiderweb.db` sqlite3 db
        if not self.engine:
            self.engine = create_engine("sqlite:///spiderweb.db")
        request.engine = self.engine
```
Now, any view that receives the incoming request object will be able to access `request.engine` and interact with the database as needed. 

> See [Writing Your Own Middleware](middleware/custom_middleware.md) for more information.

## Option 3: Using two databases

While this isn't the most delightful of options, admittedly, if your application needs to use a database that isn't something Peewee natively supports, you will want to set aside a database connection specifically for Spiderweb so that internal functions will continue to work as expected while your app uses the database you need for business logic.

## Changing the Peewee Database Target

By default, Spiderweb will create and use a SQLite db in the application directory named `spiderweb.db`. You can change this by selecting the right driver from Peewee and passing it to Spiderweb during the server instantiation, like this:

```python
from spiderweb import SpiderwebRouter
from peewee import SqliteDatabase

app = SpiderwebRouter(
    db=SqliteDatabase("my_db.sqlite")
)
```

Peewee supports the following databases at this time:

- SQLite
- MySQL
- MariaDB
- Postgres

Connecting Spiderweb to Postgres would look like this:

```python
from spiderweb import SpiderwebRouter
from peewee import PostgresqlDatabase

app = SpiderwebRouter(
    db = PostgresqlDatabase(
        'my_app',
        user='postgres',
        password='secret',
        host='10.1.0.9', 
        port=5432
    )
)
```

## Writing Peewee Models

```python
from spiderweb.db import SpiderwebModel
```

If you'd like to use Peewee, then you can use the model code written for Spiderweb. There are two special powers this grants you: migration checking and automatic database assignments.

### Automatic Database Assignments

One of the odder quirks of Peewee is that you must specify what database object a model is attached to. From [the docs](https://docs.peewee-orm.com/en/latest/peewee/quickstart.html#model-definition):

```python
from peewee import *

db = SqliteDatabase('people.db')

class Person(Model):
    name = CharField()
    birthday = DateField()

    class Meta:
        database = db # This model uses the "people.db" database.
```

Spiderweb handles the database assignment for you so that your model is added to the same database that is already in use, regardless of driver:

```python
from spiderweb.db import SpiderwebModel
from peewee import *

class Person(SpiderwebModel):
    name = CharField()
    birthday = DateField()
```

### Migration Checking

Spiderweb also watches your model and raises an error if the state of the database and your model schema differ. This check attempts to be as thorough as possible, but may not be appropriate for you; if that's the case, then add the magic variable `skip_migration_check` to the `Meta` class for your model. For example:

```python
class Person(SpiderwebModel):
    name = CharField()
    birthday = DateField()

    class Meta:
        skip_migration_check = True
```