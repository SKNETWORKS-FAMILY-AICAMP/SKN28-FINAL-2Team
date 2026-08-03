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
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    style_display = serializers.CharField(source="get_style_display", read_only=True)

    class Meta:
        model = Package
        fields = (
            "id", "name", "category", "category_display", "style", "style_display",
            "description", "thumbnail_url", "price", "duration_days", "region",
            "accommodation_included", "included_items", "course",
            "rating", "review_count", "is_active",
        )


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
