from django.db import migrations, models


def _drop_selected_package_fk(apps, schema_editor):
    """Drop only the MySQL FK constraint while preserving selected_package_id data."""
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        return

    itinerary = apps.get_model("travel", "Itinerary")
    table_name = itinerary._meta.db_table
    column_name = "selected_package_id"

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL
            """,
            [table_name, column_name],
        )
        constraints = [row[0] for row in cursor.fetchall()]

        for constraint_name in constraints:
            cursor.execute(
                "ALTER TABLE {table} DROP FOREIGN KEY {constraint}".format(
                    table=schema_editor.quote_name(table_name),
                    constraint=schema_editor.quote_name(constraint_name),
                )
            )


class Migration(migrations.Migration):
    dependencies = [("travel", "0011_remove_itinerary_budget_per_person_and_more")]

    operations = [
        # The old ForeignKey already stores its value in selected_package_id.
        # Drop the database constraint only, then change Django's state to a
        # plain integer without dropping/recreating the column (and its data).
        migrations.RunPython(
            _drop_selected_package_fk,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(model_name="itinerary", name="selected_package"),
                migrations.AddField(
                    model_name="itinerary",
                    name="selected_package_id",
                    field=models.BigIntegerField(blank=True, null=True),
                ),
            ],
        ),
        # travel_packages is an externally managed table in the travel DB.
        # Keep migration state aligned without touching that external table.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="Package"),
                migrations.CreateModel(
                    name="Package",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("package_id", models.CharField(max_length=50, unique=True)),
                        ("title", models.CharField(max_length=255)),
                        ("summary", models.TextField(blank=True, null=True)),
                        ("region", models.CharField(db_index=True, max_length=100)),
                        ("duration_days", models.PositiveSmallIntegerField()),
                        ("estimated_price", models.PositiveIntegerField(db_index=True)),
                        ("match_profile", models.JSONField()),
                        ("schema_version", models.CharField(default="1.0", max_length=20)),
                        ("is_active", models.BooleanField(default=True)),
                        ("created_at", models.DateTimeField()),
                        ("updated_at", models.DateTimeField()),
                    ],
                    options={
                        "db_table": "travel_packages",
                        "managed": False,
                        "ordering": ["id"],
                    },
                ),
            ],
        ),
    ]
