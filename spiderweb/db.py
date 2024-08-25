from peewee import Model, Field, SchemaManager, DatabaseProxy

from spiderweb.constants import DATABASE_PROXY


class MigrationsNeeded(ExceptionGroup): ...


class MigrationRequired(Exception): ...


class SpiderwebModel(Model):

    @classmethod
    def check_for_needed_migration(cls):
        current_model_fields: dict[str, Field] = cls._meta.fields
        current_db_fields = {
            c.name: {
                "data_type": c.data_type,
                "null": c.null,
                "primary_key": c.primary_key,
                "default": c.default,
            }
            for c in cls._meta.database.get_columns(cls._meta.table_name)
        }
        problems = []
        s = SchemaManager(cls, cls._meta.database)
        ctx = s._create_context()
        for field_name, field_obj in current_model_fields.items():
            db_version = current_db_fields.get(field_obj.column_name)
            if not db_version:
                problems.append(
                    MigrationRequired(f"Field {field_name} not found in DB.")
                )
                continue

            if field_obj.field_type == "VARCHAR":
                field_obj.max_length = field_obj.max_length or 255
                if (
                    cls._meta.fields[field_name].ddl_datatype(ctx).sql
                    != db_version["data_type"]
                ):
                    problems.append(
                        MigrationRequired(
                            f"CharField `{field_name}` has changed the field type."
                        )
                    )
            else:
                if (
                    cls._meta.database.get_context_options()["field_types"][
                        field_obj.field_type
                    ]
                    != db_version["data_type"]
                ):
                    problems.append(
                        MigrationRequired(
                            f"Field `{field_name}` has changed the field type."
                        )
                    )
            if field_obj.null != db_version["null"]:
                problems.append(
                    MigrationRequired(
                        f"Field `{field_name}` has changed the nullability."
                    )
                )
            if field_obj.__class__.__name__ == "BooleanField":
                if field_obj.default == False and db_version["default"] not in (
                    False,
                    None,
                    0,
                ):
                    problems.append(
                        MigrationRequired(
                            f"BooleanField `{field_name}` has changed the default value."
                        )
                    )
                elif field_obj.default == True and db_version["default"] not in (
                    True,
                    1,
                ):
                    problems.append(
                        MigrationRequired(
                            f"BooleanField `{field_name}` has changed the default value."
                        )
                    )
            else:
                if field_obj.default != db_version["default"]:
                    problems.append(
                        MigrationRequired(
                            f"Field `{field_name}` has changed the default value."
                        )
                    )

        if problems:
            raise MigrationsNeeded(f"The model {cls} requires migrations.", problems)

    class Meta:
        database = DATABASE_PROXY
