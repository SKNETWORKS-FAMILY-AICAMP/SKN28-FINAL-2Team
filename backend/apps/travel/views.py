from drf_spectacular.utils import extend_schema, extend_schema_view

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


class TouristSpotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TouristSpot.objects.all()
    serializer_class = TouristSpotSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Tourist Spots"],
        summary="관광지 목록 조회",
        responses=TouristSpotSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Tourist Spots"],
        summary="관광지 상세 조회",
        responses=TouristSpotSerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


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

    @extend_schema(
        tags=["Accommodation"],
        summary="숙소 목록 조회",
        responses=AccommodationSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Accommodation"],
        summary="숙소 상세 조회",
        responses=AccommodationSerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class RestaurantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Restaurant"],
        summary="음식점 목록 조회",
        responses=RestaurantSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Restaurant"],
        summary="음식점 상세 조회",
        responses=RestaurantSerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__icontains=category)
        return qs


class PackageViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = Package.objects.filter(is_active=True)
    serializer_class = PackageSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Package"],
        summary="패키지 목록 조회",
        responses=PackageSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Package"],
        summary="패키지 상세 조회",
        responses=PackageSerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

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


class ItineraryViewSet(viewsets.ModelViewSet):
    queryset = Itinerary.objects.none()  
    serializer_class = ItinerarySerializer
    permission_classes = [permissions.IsAuthenticated]


    @extend_schema(
        tags=["Itinerary"],
        summary="일정 목록 조회",
        responses=ItinerarySerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 상세 조회",
        responses=ItinerarySerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 생성",
        request=ItinerarySerializer,
        responses={201: ItinerarySerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 수정",
        request=ItinerarySerializer,
        responses=ItinerarySerializer,
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 일부 수정",
        request=ItinerarySerializer,
        responses=ItinerarySerializer,
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 삭제",
        responses={204: None},
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Itinerary.objects.none()

        return Itinerary.objects.filter(
            user=self.request.user
        ).prefetch_related("days__items")
    @extend_schema(
        tags=["Itinerary"],
        summary="여행 경로 조회",
        responses=ItineraryRouteSerializer(many=True)
        )
    
    @action(detail=True, methods=["get"])
    def route(self, request, pk=None):
        """여행 경로 지도 표시 — 일자별 순서대로의 좌표 목록."""
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

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 공유",

        request=None,
        responses=ItineraryShareSerializer
        )
    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        """ 일정 공유 """
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

    @extend_schema(
        tags=["Itinerary"],
        summary="공유 일정 조회",
        responses=ItinerarySerializer,
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
