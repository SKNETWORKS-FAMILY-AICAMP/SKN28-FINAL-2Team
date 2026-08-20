from rest_framework import serializers

from apps.travel.models import Package
from apps.travel.serializers import PackageSerializer

from .models import CartItem, Reservation, ReservationItem


def _get_itinerary_thumbnail_url(itinerary):
    if itinerary is None:
        return ""

    for day in itinerary.days.all().order_by("day_number"):
        first_item = (
            day.items
            .exclude(item_type="restaurant")
            .exclude(thumbnail="")
            .exclude(thumbnail__isnull=True)
            .order_by("order")
            .first()
        )

        if first_item:
            return first_item.thumbnail

    return ""


class CartItemSerializer(serializers.ModelSerializer):
    package_detail = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product_type",
            "package_db_id",
            "itinerary_id",
            "package_detail",
            "quantity",
            "option_date",
            "option_people",
            "added_at",
        )
        read_only_fields = (
            "id",
            "package_detail",
            "added_at",
        )

    def get_package_detail(self, obj):
        if obj.product_type == CartItem.ProductType.CUSTOM_ITINERARY:
            itinerary = obj.itinerary

            return {
                "id": f"custom-{obj.itinerary_id}",
                "package_id": f"CUSTOM-{obj.itinerary_id}",
                "name": obj.product_name or "Custom itinerary package",
                "description": "확정한 일정 그대로 예약하는 자유패키지입니다.",
                "price": obj.unit_price,
                "thumbnail_url": _get_itinerary_thumbnail_url(itinerary),
                "isCustom": True,
            }

        package = (
            Package.objects.using("travel")
            .filter(
                id=obj.package_db_id,
                is_active=True,
            )
            .first()
        )

        if package is None:
            return None

        return PackageSerializer(package).data


class CartSerializer(serializers.Serializer):
    items = CartItemSerializer(many=True)
    total_price = serializers.IntegerField()


class CartItemCreateSerializer(serializers.Serializer):
    product_type = serializers.ChoiceField(
        choices=CartItem.ProductType.choices,
        default=CartItem.ProductType.STORED_PACKAGE,
    )
    package_id = serializers.IntegerField(required=False)
    itinerary_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        product_type = attrs["product_type"]

        if product_type == CartItem.ProductType.STORED_PACKAGE:
            if not attrs.get("package_id"):
                raise serializers.ValidationError({"package_id": "package_id is required."})
        elif not attrs.get("itinerary_id"):
            raise serializers.ValidationError({"itinerary_id": "itinerary_id is required."})

        return attrs

    def validate_package_id(self, value):
        exists = (
            Package.objects.using("travel")
            .filter(
                id=value,
                is_active=True,
            )
            .exists()
        )

        if not exists:
            raise serializers.ValidationError(
                "존재하지 않거나 비활성화된 패키지입니다."
            )

        return value


class CartItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = (
            "quantity",
            "option_date",
            "option_people",
        )

    def validate_quantity(self, value):
        if value < 1 or value > 9:
            raise serializers.ValidationError(
                "수량은 1개 이상 9개 이하로 설정해주세요."
            )

        return value

    def validate_option_people(self, value):
        if value < 1 or value > 20:
            raise serializers.ValidationError(
                "인원은 1명 이상 20명 이하로 설정해주세요."
            )

        return value


class ReservationItemSerializer(serializers.ModelSerializer):
    schedule = serializers.SerializerMethodField()
    accommodation = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = ReservationItem
        fields = (
            "id",
            "product_type",
            "package_db_id",
            "package_id",
            "name",
            "display_name",
            "thumbnail_url",
            "price",
            "quantity",
            "option_date",
            "option_people",
            "accommodation",
            "schedule",
        )

    @staticmethod
    def _is_custom(obj):
        return (
            obj.product_type == CartItem.ProductType.CUSTOM_ITINERARY
            or str(obj.package_id or "").upper().startswith("CUSTOM-")
        )

    def _get_stored_package(self, obj):
        cache_name = "_resolved_reservation_package"
        if hasattr(obj, cache_name):
            return getattr(obj, cache_name)

        filters = {}
        if obj.package_db_id:
            filters["id"] = obj.package_db_id
        elif obj.package_id:
            filters["package_id"] = obj.package_id
        else:
            package = None
            setattr(obj, cache_name, package)
            return package

        package = (
            Package.objects.using("travel")
            .filter(**filters)
            .first()
        )
        setattr(obj, cache_name, package)
        return package

    def get_display_name(self, obj):
        if self._is_custom(obj):
            itinerary = obj.reservation.itinerary
            return itinerary.title if itinerary and itinerary.title else obj.name

        package = self._get_stored_package(obj)
        return package.title if package and package.title else obj.name

    def get_thumbnail_url(self, obj):
        if self._is_custom(obj):
            return _get_itinerary_thumbnail_url(obj.reservation.itinerary)

        package = self._get_stored_package(obj)
        if package is None:
            return ""

        return PackageSerializer().get_thumbnail_url(package)

    def get_accommodation(self, obj):
        if self._is_custom(obj):
            itinerary = obj.reservation.itinerary
            if itinerary is None:
                return None

            itinerary_state = (itinerary.engine_state or {}).get("itinerary") or {}
            return itinerary_state.get("hotel")

        package_db_id = obj.package_db_id
        if not package_db_id and obj.package_id:
            package_db_id = (
                Package.objects.using("travel")
                .filter(package_id=obj.package_id, is_active=True)
                .values_list("id", flat=True)
                .first()
            )

        if not package_db_id:
            return None

        from django.db import connections

        with connections["travel"].cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.title,
                    p.addr1,
                    p.addr2,
                    p.latitude,
                    p.longitude,
                    pi.content_id
                FROM package_items pi
                LEFT JOIN places p ON p.content_id = pi.content_id
                WHERE pi.package_db_id = %s
                  AND pi.item_type = 'hotel'
                ORDER BY pi.day_no, pi.sequence
                LIMIT 1
                """,
                [package_db_id],
            )
            row = cursor.fetchone()

        if row is None:
            return None

        title, addr1, addr2, latitude, longitude, content_id = row
        address = " ".join(part for part in (addr1, addr2) if part)
        return {
            "content_id": content_id,
            "title": title or "숙소",
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
        }

    def get_schedule(self, obj):
        if not self.context.get("include_schedule", True):
            return []
        
        if self._is_custom(obj):
            return []

        package_db_id = obj.package_db_id
        if not package_db_id and obj.package_id:
            package_db_id = (
                Package.objects.using("travel")
                .filter(package_id=obj.package_id, is_active=True)
                .values_list("id", flat=True)
                .first()
            )

        if not package_db_id:
            return []

        from django.db import connections

        with connections["travel"].cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    pi.day_no,
                    pi.sequence,
                    pi.item_type,
                    pi.content_id,
                    pi.stay_minutes,
                    p.title,
                    p.addr1,
                    p.addr2,
                    p.latitude,
                    p.longitude,
                    (
                        SELECT COALESCE(NULLIF(img.image_url, ''), img.thumbnail_url)
                        FROM place_images img
                        WHERE img.content_id = pi.content_id
                          AND (img.image_url IS NOT NULL OR img.thumbnail_url IS NOT NULL)
                        ORDER BY img.display_order
                        LIMIT 1
                    )
                FROM package_items pi
                LEFT JOIN places p ON p.content_id = pi.content_id
                WHERE pi.package_db_id = %s
                  AND pi.day_no IS NOT NULL
                ORDER BY pi.day_no, pi.sequence
                """,
                [package_db_id],
            )
            rows = cursor.fetchall()

        days = {}
        for row in rows:
            (
                day_no,
                sequence,
                item_type,
                content_id,
                stay_minutes,
                title,
                addr1,
                addr2,
                latitude,
                longitude,
                thumbnail,
            ) = row
            address = " ".join(part for part in (addr1, addr2) if part)
            days.setdefault(day_no, []).append({
                "sequence": sequence,
                "item_type": item_type,
                "content_id": content_id,
                "stay_minutes": stay_minutes,
                "title": title or f"장소 {content_id}",
                "description": address,
                "latitude": latitude,
                "longitude": longitude,
                "thumbnail": thumbnail or "",
            })

        return [
            {
                "day": day_no,
                "items": items,
            }
            for day_no, items in sorted(days.items())
        ]


class ReservationSerializer(serializers.ModelSerializer):
    items = ReservationItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Reservation
        fields = (
            "id",
            "itinerary",
            "total_price",
            "payment_method",
            "status",
            "status_display",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "total_price",
            "status",
            "created_at",
            "updated_at",
        )


class ReservationCreateSerializer(serializers.Serializer):
    """
    장바구니를 예약으로 전환하거나,
    package_ids를 직접 넘겨 바로 예약할 수 있다.
    """

    itinerary_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )

    package_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

    cart_item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

    payment_method = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    start_date = serializers.DateField(
        required=False,
        allow_null=True,
    )

    people_count = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
    )
