import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservation", "0001_initial"),
        ("travel", "0002_place_touristspot_source_id_alter_itinerary_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="product_type",
            field=models.CharField(
                choices=[
                    ("stored_package", "Stored package"),
                    ("custom_itinerary", "Custom itinerary"),
                ],
                default="stored_package",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="cartitem",
            name="itinerary",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cart_product_items",
                to="travel.itinerary",
            ),
        ),
        migrations.AddField(
            model_name="cartitem",
            name="product_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="cartitem",
            name="unit_price",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="cartitem",
            name="package_db_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reservationitem",
            name="product_type",
            field=models.CharField(
                choices=[
                    ("stored_package", "Stored package"),
                    ("custom_itinerary", "Custom itinerary"),
                ],
                default="stored_package",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="reservationitem",
            name="package_db_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
