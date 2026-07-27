from drf_spectacular.utils import extend_schema

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response

from .models import Accommodation, Itinerary, Package, Restaurant, TouristSpot
from .serializers import (
    AccommodationSerializer,
    ItineraryRouteSerializer,
    ItinerarySerializer,
    ItineraryShareSerializer,
    PackageSerializer,
    RestaurantSerializer,
    TouristSpotSerializer,
)


# =========================================================
# 카탈로그 (읽기 전용, 로그인 불필요)
# M005-F-003 패키지 목록, M005-F-004 패키지 상세, M005-F-005 필터/탭
# =========================================================

class TouristSpotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TouristSpot.objects.all()
    serializer_class = TouristSpotSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        tag = self.request.query_params.get("tag")
        keyword = self.request.query_params.get("q")
        if tag:
            qs = qs.filter(tags__icontains=tag)
        if keyword:
            qs = qs.filter(name__icontains=keyword)
        return qs


class AccommodationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Accommodation.objects.all()
    serializer_class = AccommodationSerializer
    permission_classes = [permissions.AllowAny]


class RestaurantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__icontains=category)
        return qs


class PackageViewSet(viewsets.ReadOnlyModelViewSet):
    """M005-F-003 패키지 목록 / M005-F-004 패키지 상세 / M005-F-005 필터."""

    queryset = Package.objects.filter(is_active=True)
    serializer_class = PackageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        style = self.request.query_params.get("style")
        category = self.request.query_params.get("category")
        duration_days = self.request.query_params.get("duration_days")
        max_price = self.request.query_params.get("max_price")

        if style:
            qs = qs.filter(style=style)
        if category:
            qs = qs.filter(category=category)
        if duration_days:
            qs = qs.filter(duration_days=duration_days)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        return qs


# =========================================================
# 최종 일정 (로그인 필요, 본인 소유만 접근)
# =========================================================

class ItineraryViewSet(viewsets.ModelViewSet):
    """M004 최종 일정표 CRUD (본인 소유 일정만 조회/수정/삭제 가능)."""

    queryset = Itinerary.objects.none()  # 스키마 생성 시 PK 타입 추론용 (실제 조회는 get_queryset 사용)
    serializer_class = ItinerarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Itinerary.objects.none()
        return Itinerary.objects.filter(user=self.request.user).prefetch_related("days__items")

    @extend_schema(responses=ItineraryRouteSerializer(many=True))
    @action(detail=True, methods=["get"])
    def route(self, request, pk=None):
        """M004-F-006 여행 경로 지도 표시 — 일자별 순서대로의 좌표 목록."""
        itinerary = self.get_object()
        result = []
        for day in itinerary.days.all():
            points = [
                {
                    "order": item.order,
                    "title": item.title,
                    "latitude": item.latitude,
                    "longitude": item.longitude,
                }
                for item in day.items.all()
                if item.latitude is not None and item.longitude is not None
            ]
            result.append({"day_number": day.day_number, "points": points})
        return Response(result)

    @extend_schema(request=None, responses=ItineraryShareSerializer)
    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        """M004-F-008 일정 공유 — 공유 토큰을 발급한다."""
        itinerary = self.get_object()
        token = itinerary.ensure_share_token()
        return Response(
            {
                "share_token": str(token),
                "share_path": f"/api/travel/itineraries/shared/{token}/",
            },
            status=status.HTTP_200_OK,
        )


class SharedItineraryAPIView(RetrieveAPIView):
    """공유 링크로 접근하는 읽기 전용 뷰 (로그인 불필요)."""

    serializer_class = ItinerarySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "share_token"
    lookup_url_kwarg = "token"
    queryset = Itinerary.objects.exclude(share_token__isnull=True).prefetch_related("days__items")
