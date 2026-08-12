from django.db import migrations, models


def remove_legacy_package_foreign_key(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return

    itinerary = apps.get_model("travel", "Itinerary")
    table_name = itinerary._meta.db_table
    column_name = "selected_package_id"

    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(
            cursor,
            table_name,
        )

    quote_name = schema_editor.quote_name
    for constraint_name, details in constraints.items():
        if details.get("foreign_key") and details["columns"] == [column_name]:
            schema_editor.execute(
                f"ALTER TABLE {quote_name(table_name)} "
                f"DROP FOREIGN KEY {quote_name(constraint_name)}"
            )


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("travel", "0012_merge_20260807_0954"),
    ]

    operations = [
        migrations.RunPython(
            remove_legacy_package_foreign_key,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="itinerary",
            name="selected_package",
            field=models.BigIntegerField(
                blank=True,
                db_column="selected_package_id",
                null=True,
            ),
        ),
    ]
