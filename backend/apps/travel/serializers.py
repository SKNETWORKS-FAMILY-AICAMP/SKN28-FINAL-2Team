import copy

from rest_framework import serializers

from drf_spectacular.utils import extend_schema_field

from .models import Itinerary, ItineraryDay, ItineraryItem, Package


def _csv_values(value):
    return {
        item.strip().lower()
        for item in str(value or "").split(",")
        if item.strip()
    }


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
            "id", "package_id", "name", "description", "price", "region", "duration_days",
            "companion", "tags",
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
        companions = _csv_values(obj.companion)
        tags = _csv_values(obj.tags)

        if "family" in companions:
            return "family"

        if "experience" in tags or "activity" in tags:
            return "activity"

        if "food" in tags:
            return "food"

        if "nature" in tags:
            return "healing"

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
    def get_thumbnail(self, obj):
        from django.db import connections

        with connections["travel"].cursor() as cursor:
            cursor.execute(
                """
                SELECT 
                    p.content_id,
                    img.image_url,
                    img.thumbnail_url
                FROM places p
                LEFT JOIN place_images img
                    ON img.content_id = p.content_id
                WHERE p.title = %s
                ORDER BY img.display_order
                LIMIT 1
                """,
                [obj.title],
            )

            row = cursor.fetchone()

        if row:
            return row[1] or row[2] or ""

        return ""


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
        engine_days_data = copy.deepcopy(days_data) if days_data is not None else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if days_data is not None:
            self._sync_days(instance, days_data)
            self._sync_engine_state_days(instance, engine_days_data)

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

    @staticmethod
    def _sync_engine_state_days(itinerary, days_data):
        """Keep package recommendation input aligned with direct schedule edits."""

        state = copy.deepcopy(itinerary.engine_state)
        if not isinstance(state, dict) or not isinstance(state.get("itinerary"), dict):
            return

        old_days = state["itinerary"].get("days") or []
        old_days_by_number = {
            int(day.get("day")): day
            for day in old_days
            if isinstance(day, dict) and day.get("day") is not None
        }
        old_stops_by_title = {}
        for day in old_days:
            for stop in day.get("stops") or []:
                title = str(stop.get("title") or "").strip()
                if title:
                    old_stops_by_title[title] = stop

        role_by_item_type = {
            "spot": "visit",
            "restaurant": "food",
            "accommodation": "lodge",
            "activity": "activity",
        }
        new_days = []
        used_content_ids = []

        for day_data in days_data or []:
            day_number = int(day_data.get("day_number") or len(new_days) + 1)
            old_day = old_days_by_number.get(day_number, {})
            new_stops = []

            for index, item_data in enumerate(day_data.get("items") or [], start=1):
                title = str(item_data.get("title") or "").strip()
                old_stop = old_stops_by_title.get(title, {})
                content_id = old_stop.get("content_id")

                linked_spot = item_data.get("spot")
                if content_id is None and linked_spot is not None:
                    source_id = getattr(linked_spot, "source_id", None)
                    if source_id and str(source_id).isdigit():
                        content_id = int(source_id)

                if content_id is None:
                    continue

                stop = copy.deepcopy(old_stop)
                stop.update(
                    {
                        "sequence": index,
                        "title": title,
                        "content_id": int(content_id),
                        "role": role_by_item_type.get(
                            str(item_data.get("item_type") or ""),
                            stop.get("role", "visit"),
                        ),
                    }
                )
                if item_data.get("time"):
                    stop["start_time"] = str(item_data["time"])
                new_stops.append(stop)
                used_content_ids.append(int(content_id))

            new_days.append(
                {
                    "day": day_number,
                    "title": old_day.get("title", f"DAY {day_number}"),
                    "stops": new_stops,
                }
            )

        state["itinerary"]["days"] = new_days
        state["used_content_ids"] = list(dict.fromkeys(used_content_ids))
        itinerary.engine_state = state
        itinerary.save(update_fields=["engine_state"])


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
