# Generated manually: 여행 스타일을 미리 정해둔 카테고리(choices)로 제한하지 않고
# 자유 입력 텍스트 그대로 저장하도록 변경 (필터링 없이 RAG 검색 조건으로 사용).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('travel', '0012_itinerary_age_group'),
    ]

    operations = [
        migrations.AlterField(
            model_name='itinerary',
            name='style',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
