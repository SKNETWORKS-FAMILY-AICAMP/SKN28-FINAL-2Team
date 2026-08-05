from rest_framework import serializers

from drf_spectacular.utils import extend_schema_field

from .models import Accommodation, Itinerary, ItineraryDay, ItineraryItem, Package, Restaurant, TouristSpot


class TouristSpotSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()

    class Meta:
        model = TouristSpot
        fields = (
            "id", "name", "address", "description", "image_url",
            "tags", "latitude", "longitude",
        )

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_tags(self, obj):
        return obj.tag_list()


class AccommodationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accommodation
        fields = (
            "id", "name", "address", "description", "image_url",
            "price_per_night", "rating", "review_count", "latitude", "longitude",
        )


class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = (
            "id", "name", "address", "description", "image_url", "category",
            "price_range", "rating", "review_count", "latitude", "longitude",
        )

class PackageSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="title", read_only=True)
    description = serializers.CharField(source="summary", read_only=True)
    price = serializers.IntegerField(source="estimated_price", read_only=True)

    accommodation_included = serializers.SerializerMethodField()
    style = serializers.SerializerMethodField()
    style_display = serializers.SerializerMethodField()
    course = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = (
            "id", "package_id", "name", "description", "price", "region", "duration_days", "match_profile", 
            "thumbnail_url", "accommodation_included", "style", "style_display", "course", "is_active",
        )

    def get_accommodation_included(self, obj):
        from django.db import connections

        with connections["travel"].cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM package_items
                    WHERE package_db_id = %s
                      AND item_type = 'hotel'
                )
                """,
                [obj.id],
            )
            return bool(cursor.fetchone()[0])

    def get_style(self, obj):
        profile = obj.match_profile or {}
        paces = profile.get("paces", [])
        themes = profile.get("themes", [])
        party_types = profile.get("party_types", [])

        if "with_children" in party_types or "family_group" in party_types:
            return "family"

        if "relaxed" in paces:
            return "healing"

        if "experience" in themes:
            return "activity"

        if "food" in themes or "market_shopping" in themes:
            return "food"

        return ""

    def get_style_display(self, obj):
        labels = {
            "family": "가족여행",
            "healing": "힐링여행",
            "activity": "액티비티",
            "food": "맛집여행",
        }
        return labels.get(self.get_style(obj), "")

    def get_thumbnail_url(self, obj):
        from django.db import connections

        with connections["travel"].cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(NULLIF(img.image_url, ''), img.thumbnail_url)
                FROM package_items pi
                JOIN place_images img
                ON img.content_id = pi.content_id
                WHERE pi.package_db_id = %s
                AND pi.item_type = 'tourism'
                AND (
                    img.thumbnail_url IS NOT NULL
                    OR img.image_url IS NOT NULL
                )
                ORDER BY
                CASE
                    WHEN pi.day_no IS NULL THEN 999
                    ELSE pi.day_no
                END,
                CASE
                    WHEN pi.sequence IS NULL THEN 999
                    ELSE pi.sequence
                END,
                img.display_order
                LIMIT 1
                """,
                [obj.id],
            )

            row = cursor.fetchone()

        return row[0] if row else ""
    
    def get_course(self, obj):
        from django.db import connections

        with connections["travel"].cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    pi.day_no,
                    pi.sequence,
                    pi.item_type,
                    pi.content_id,
                    p.title,
                    p.addr1,
                    p.addr2
                FROM package_items pi
                LEFT JOIN places p
                    ON p.content_id = pi.content_id
                WHERE pi.package_db_id = %s
                AND pi.day_no IS NOT NULL
                ORDER BY pi.day_no, pi.sequence
                """,
                [obj.id],
            )

            rows = cursor.fetchall()

        course_by_day = {}

        for (
            day_no,
            sequence,
            item_type,
            content_id,
            title,
            addr1,
            addr2,
        ) in rows:
            course_by_day.setdefault(day_no, []).append(
                {
                    "sequence": sequence,
                    "item_type": item_type,
                    "content_id": content_id,
                    "title": title or f"장소 {content_id}",
                    "address": " ".join(
                        part for part in [addr1, addr2] if part
                    ),
                }
            )

        return [
            {
                "day": day_no,
                "items": items,
            }
            for day_no, items in sorted(course_by_day.items())
        ]
    
class ItineraryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItineraryItem
        fields = (
            "id", "order", "time", "item_type", "title", "description",
            "thumbnail", "cost", "spot", "restaurant", "accommodation",
            "latitude", "longitude", "memo",
        )


class ItineraryDaySerializer(serializers.ModelSerializer):
    items = ItineraryItemSerializer(many=True, required=False)

    class Meta:
        model = ItineraryDay
        fields = ("id", "day_number", "date", "items")


class CostBreakdownItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    amount = serializers.IntegerField()


class ItinerarySerializer(serializers.ModelSerializer):

    days = ItineraryDaySerializer(many=True, required=False)
    total_cost = serializers.ReadOnlyField()
    duration_label = serializers.ReadOnlyField()
    style_display = serializers.CharField(source="get_style_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    companion_type_display = serializers.CharField(source="get_companion_type_display", read_only=True)
    transport_display = serializers.CharField(source="get_transport_display", read_only=True)
    cost_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = Itinerary
        fields = (
            "id", "title", "subtitle", "start_date", "end_date",
            "companion_type", "companion_type_display",
            "companion_count", "transport", "transport_display", "style", "style_display", "budget_per_person",
            "accommodation_cost", "transport_cost", "activity_cost",
            "food_cost", "etc_cost", "total_cost", "cost_breakdown",
            "selected_package", "status", "status_display", "is_public",
            "share_token", "duration_label", "days",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "share_token", "created_at", "updated_at")

    @extend_schema_field(CostBreakdownItemSerializer(many=True))
    def get_cost_breakdown(self, obj):
        return [
            {"label": "숙소", "amount": obj.accommodation_cost},
            {"label": "렌터카", "amount": obj.transport_cost},
            {"label": "액티비티", "amount": obj.activity_cost},
            {"label": "식비", "amount": obj.food_cost},
            {"label": "기타", "amount": obj.etc_cost},
        ]

    def create(self, validated_data):
        days_data = validated_data.pop("days", [])
        itinerary = Itinerary.objects.create(**validated_data)
        self._sync_days(itinerary, days_data)
        return itinerary


    def update(self, instance, validated_data):
        days_data = validated_data.pop("days", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if days_data is not None:
            self._sync_days(instance, days_data)

        return instance

    @staticmethod
    def _sync_days(itinerary, days_data):
        """전달된 days/items로 전체를 교체 """
        if not days_data:
            return

        itinerary.days.all().delete()

        for day_data in days_data:
            items_data = day_data.pop("items", [])
            day = ItineraryDay.objects.create(itinerary=itinerary, **day_data)
            for idx, item_data in enumerate(items_data):
                item_data.setdefault("order", idx)
                ItineraryItem.objects.create(day=day, **item_data)


class ItineraryRouteSerializer(serializers.Serializer):
    """일자별 순서대로의 좌표 목록."""

    day_number = serializers.IntegerField()
    points = serializers.ListField(
        child=serializers.DictField(),
    )


class ItineraryShareSerializer(serializers.Serializer):
    share_token = serializers.UUIDField()
    share_path = serializers.CharField()

class ItineraryRevisionSerializer(serializers.Serializer):
    message = serializers.CharField()