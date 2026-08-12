from rest_framework import serializers

from .models import History


class HistorySerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = History
        fields = ("id", "code", "action", "action_display", "detail", "date", "time", "created_at")
        read_only_fields = ("id", "code", "created_at")
        extra_kwargs = {
            "date": {"required": False},
            "time": {"required": False},
        }
