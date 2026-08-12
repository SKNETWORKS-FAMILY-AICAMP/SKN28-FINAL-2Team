from rest_framework import serializers

from .models import Itinerary, ItineraryDay, ItineraryItem, Package
from .kakao_route_service import get_kakao_route_path


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
            "id",
            "package_id",
            "name",
            "description",
            "price",
            "region",
            "duration_days",
            "companion",
            "tags",
            "thumbnail_url",
            "accommodation_included",
            "style",
            "style_display",
            "course",
            "is_active",
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
                    p.addr2,
                    p.latitude,
                    p.longitude
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
            latitude,
            longitude,
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
                    "latitude": latitude,
                    "longitude": longitude,
                }
            )

        result = []

        for day_no, items in sorted(course_by_day.items()):
            valid_items = [
                item
                for item in items
                if (
                    item.get("latitude") is not None
                    and item.get("longitude") is not None
                )
            ]

            valid_items.sort(
                key=lambda item: int(
                    item.get("sequence") or 0
                )
            )

            day_path = []

            for index in range(len(valid_items) - 1):
                origin = valid_items[index]
                destination = valid_items[index + 1]

                try:
                    segment_path = get_kakao_route_path(
                        origin,
                        destination,
                    )
                except RuntimeError as exc:
                    print(
                        "[Kakao] 추천 패키지 경로 조회 실패:",
                        origin.get("title"),
                        "→",
                        destination.get("title"),
                        exc,
                    )
                    continue

                if not segment_path:
                    continue

                if day_path:
                    day_path.extend(segment_path[1:])
                else:
                    day_path.extend(segment_path)

            print(
                "[Kakao] 추천 패키지 경로 생성:",
                f"DAY {day_no}",
                f"{len(day_path)} points",
            )

            result.append(
                {
                    "day": day_no,
                    "items": items,
                    "path": day_path,
                }
            )

        return result
    
class ItineraryItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = ItineraryItem
        fields = (
            "id", "order", "time", "item_type", "title", "description",
            "thumbnail", "spot", "restaurant", "accommodation",
            "latitude", "longitude", "memo",
        )

class ItineraryDaySerializer(serializers.ModelSerializer):
    items = ItineraryItemSerializer(many=True, required=False)

    class Meta:
        model = ItineraryDay
        fields = ("id", "day_number", "date", "items")

class ItinerarySerializer(serializers.ModelSerializer):
    title = serializers.CharField(required=False,allow_blank=True)
    days = ItineraryDaySerializer(many=True, required=False)
    duration_label = serializers.ReadOnlyField()
    # style은 더 이상 choices로 제한된 카테고리가 아니라 자유 입력 텍스트이므로
    # 별도의 "표시용" 값이 없다. style 값 자체를 그대로 노출한다.
    style_display = serializers.CharField(source="style", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    companion_type_display = serializers.CharField(source="get_companion_type_display", read_only=True)
    booked_product_type = serializers.SerializerMethodField()
    booked_package_db_id = serializers.SerializerMethodField()
    booked_price = serializers.SerializerMethodField()


    class Meta:
        model = Itinerary
        fields = (
            "id", "title", "subtitle", "start_date", "end_date",
            "companion_type", "companion_type_display",
            "companion_count",  "age_group", "style", "style_display",
            "selected_package", "status", "status_display", "is_public",
            "share_token", "duration_label", "days",
            "created_at", "updated_at", "booked_product_type", "booked_package_db_id", "booked_price"
        )
        read_only_fields = ("id", "share_token", "created_at", "updated_at")

    def get_booked_product_type(self, obj):
        reservation = (
            obj.reservations
            .filter(status="confirmed")
            .prefetch_related("items")
            .order_by("-created_at")
            .first()
        )

        if not reservation:
            return None

        item = reservation.items.first()

        if not item:
            return None

        return item.product_type


    def get_booked_package_db_id(self, obj):
        reservation = (
            obj.reservations
            .filter(status="confirmed")
            .prefetch_related("items")
            .order_by("-created_at")
            .first()
        )

        if not reservation:
            return None

        item = reservation.items.first()

        if not item:
            return None

        return item.package_db_id

    def get_booked_price(self, obj):
        reservation = (
            obj.reservations
            .filter(status="confirmed")
            .prefetch_related("items")
            .order_by("-created_at")
            .first()
        )

        if not reservation:
            return None

        item = reservation.items.first()

        if not item:
            return None

        return item.price

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
    """
    일자별 최적 방문 순서와 실제 자동차 도로 경로.
    """

    day_number = serializers.IntegerField()

    points = serializers.ListField(
        child=serializers.DictField(),
    )

    path = serializers.ListField(
        child=serializers.DictField(),
    )


class ItineraryShareSerializer(serializers.Serializer):
    share_token = serializers.UUIDField()
    share_path = serializers.CharField()

class ItineraryRevisionSerializer(serializers.Serializer):
    message = serializers.CharField()