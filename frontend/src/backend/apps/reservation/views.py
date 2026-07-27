from django.db import transaction
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema

from rest_framework import permissions, status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.travel.models import Itinerary, Package

from .models import CartItem, Reservation, ReservationItem
from .serializers import (
    CartItemCreateSerializer,
    CartItemSerializer,
    CartSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
)


# =========================================================
# 장바구니 (M005-F-007 필수)
# =========================================================

class CartAPIView(APIView):
    """GET: 장바구니 조회 / POST: 패키지 담기."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=CartSerializer)
    def get(self, request):
        items = CartItem.objects.filter(user=request.user).select_related("package")
        serializer = CartItemSerializer(items, many=True)
        total = sum(item.package.price for item in items)
        return Response({"items": serializer.data, "total_price": total})

    @extend_schema(request=CartItemCreateSerializer, responses=CartItemSerializer)
    def post(self, request):
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        package = serializer.validated_data["package_id"]

        item, created = CartItem.objects.get_or_create(user=request.user, package=package)
        return Response(
            CartItemSerializer(item).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CartItemDetailAPIView(APIView):
    """DELETE: 장바구니에서 항목 제거."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        item = get_object_or_404(CartItem, pk=pk, user=request.user)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# =========================================================
# 예약 요청 (M005-F-008 선택, 시연 / M001-F-006 예약 내역 조회)
# =========================================================

class ReservationListCreateAPIView(ListAPIView):
    """GET: 내 예약 내역 조회 / POST: 예약 요청(시연)."""

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Reservation.objects.filter(user=self.request.user).prefetch_related("items")

    @extend_schema(
        request=ReservationCreateSerializer,
        responses={201: ReservationSerializer, 400: None},
    )
    @transaction.atomic
    def post(self, request):
        serializer = ReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        package_ids = data.get("package_ids")

        if package_ids:
            packages = list(Package.objects.filter(id__in=package_ids, is_active=True))
        else:
            # package_ids가 없으면 장바구니 전체를 예약 요청으로 전환한다.
            cart_items = CartItem.objects.filter(user=request.user).select_related("package")
            packages = [ci.package for ci in cart_items]

        if not packages:
            return Response(
                {"detail": "예약할 패키지가 없습니다. 장바구니에 패키지를 담거나 package_ids를 지정해주세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        itinerary = None
        itinerary_id = data.get("itinerary_id")
        if itinerary_id:
            itinerary = get_object_or_404(Itinerary, pk=itinerary_id, user=request.user)

        total_price = sum(p.price for p in packages)

        reservation = Reservation.objects.create(
            user=request.user,
            itinerary=itinerary,
            total_price=total_price,
            payment_method=data.get("payment_method") or "신용카드 (**** **** **** 1234)",
            status=Reservation.Status.CONFIRMED,  # 시연: 결제 연동 없이 즉시 확정 처리
        )

        ReservationItem.objects.bulk_create(
            [
                ReservationItem(reservation=reservation, package=p, name=p.name, price=p.price, quantity=1)
                for p in packages
            ]
        )

        # 예약으로 전환된 패키지는 장바구니에서 제거한다.
        CartItem.objects.filter(user=request.user, package__in=packages).delete()

        return Response(ReservationSerializer(reservation).data, status=status.HTTP_201_CREATED)


class ReservationDetailAPIView(RetrieveAPIView):
    """예약 상세 조회."""

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Reservation.objects.filter(user=self.request.user).prefetch_related("items")
