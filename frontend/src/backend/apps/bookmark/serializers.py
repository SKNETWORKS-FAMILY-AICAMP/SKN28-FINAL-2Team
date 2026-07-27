from rest_framework import serializers

from apps.travel.models import Package
from apps.travel.serializers import PackageSerializer

from .models import Bookmark


class BookmarkSerializer(serializers.ModelSerializer):
    package_detail = PackageSerializer(source="package", read_only=True)

    class Meta:
        model = Bookmark
        fields = ("id", "package", "package_detail", "created_at")
        read_only_fields = ("id", "created_at")


class BookmarkCreateSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(
        source="package", queryset=Package.objects.filter(is_active=True)
    )
