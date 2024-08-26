from peewee import *
from playhouse.migrate import SqliteMigrator, migrate

from spiderweb.db import SpiderwebModel

db = SqliteDatabase("people.db")
migrator = SqliteMigrator(db)


class Person(SpiderwebModel):
    name = CharField()
    birthday = DateField()

    class Meta:
        database = db  # This model uses the "people.db" database.


class Pet(SpiderwebModel):
    owner = ForeignKeyField(Person, backref="pets")
    name = CharField(max_length=40)
    animal_type = CharField()
    age = IntegerField(null=True)
    favorite_color = CharField(null=True)

    class Meta:
        database = db  # this model uses the "people.db" database


if __name__ == "__main__":
    db.connect()
    Pet.check_for_needed_migration()
    # try:
    #     Pet.check_for_needed_migration()
    # except:
    #     migrate(
    #         migrator.add_column(
    #             Pet._meta.table_name, 'favorite_color', CharField(null=True)
    #         ),
    #     )
    db.create_tables([Person, Pet])
