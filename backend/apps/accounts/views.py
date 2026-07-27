from drf_spectacular.utils import extend_schema

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import (
    ErrorSerializer,
    LogoutSerializer,
    SocialLoginSerializer,
    TokenPairSerializer,
    UserMeSerializer,
)
from .services import google_login, kakao_login


class GoogleLoginAPIView(APIView):

    @extend_schema(
        request=SocialLoginSerializer,
        responses={200: TokenPairSerializer, 400: ErrorSerializer},
    )
    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = google_login(serializer.validated_data["token"])

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "detail": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class KakaoLoginAPIView(APIView):

    @extend_schema(
        request=SocialLoginSerializer,
        responses={200: TokenPairSerializer, 400: ErrorSerializer},
    )
    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = kakao_login(serializer.validated_data["token"])

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "detail": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class LogoutAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LogoutSerializer,
        responses={205: None, 400: ErrorSerializer},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserMeSerializer)
    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(request=UserMeSerializer, responses=UserMeSerializer)
    def patch(self, request):
        serializer = UserMeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
