from rest_framework import serializers

from .models import User


class SocialLoginSerializer(serializers.Serializer):
    token = serializers.CharField()


class TokenPairSerializer(serializers.Serializer):
    """소셜 로그인 성공 시 응답 형태"""

    access = serializers.CharField()
    refresh = serializers.CharField()


class ErrorSerializer(serializers.Serializer):
    """오류 응답 형태"""

    detail = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class UserMeSerializer(serializers.ModelSerializer):
    """사용자 정보 관리"""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "nickname",
            "profile_image",
            "provider",
            "phone",
            "preferred_style",
            "preferred_budget",
            "date_joined",
        )
        read_only_fields = ("id", "email", "provider", "date_joined")