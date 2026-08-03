# Generated manually to add TREKKING style choice

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('travel', '0003_itinerary_companion_type_itinerary_transport'),
    ]

    operations = [
        migrations.AlterField(
            model_name='itinerary',
            name='style',
            field=models.CharField(
                blank=True,
                choices=[
                    ('family', '가족여행'),
                    ('healing', '힐링여행'),
                    ('activity', '액티비티'),
                    ('food', '맛집여행'),
                    ('trekking', '트레킹'),
                ],
                max_length=20,
            ),
        ),
    ]
