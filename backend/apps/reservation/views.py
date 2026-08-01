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



class CartAPIView(APIView):
    
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Cart"],
        summary="장바구니 조회",
        responses=CartSerializer
        )
    def get(self, request):
        items = CartItem.objects.filter(user=request.user).select_related("package")
        serializer = CartItemSerializer(items, many=True)
        total = sum(item.package.price for item in items)
        return Response({"items": serializer.data, "total_price": total})

    @extend_schema(
        tags=["Cart"],
        summary="장바구니 추가",    
        request=CartItemCreateSerializer,
        responses=CartItemSerializer
        )
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

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Cart"],
        summary="장바구니 삭제",    
        responses={204: None}
        )
    def delete(self, request, pk):
        item = get_object_or_404(CartItem, pk=pk, user=request.user)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReservationListCreateAPIView(ListAPIView):

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Reservation.objects.filter(user=self.request.user).prefetch_related("items")

    @extend_schema(
        tags=["Reservation"],
        summary="예약 생성",
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


@extend_schema(
    tags=["Reservation"],
    summary="예약 상세 조회",
)
class ReservationDetailAPIView(RetrieveAPIView):

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Reservation.objects.filter(
            user=self.request.user
        ).prefetch_related("items")

@extend_schema(
    tags=["Reservation"],
    summary="예약 취소",
    request=None,
    responses={
        200: ReservationSerializer,
        400: None,
        404: None,
    },
)
class ReservationCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        reservation = get_object_or_404(
            Reservation.objects.prefetch_related("items"),
            pk=pk,
            user=request.user,
        )

        if reservation.status == Reservation.Status.CANCELLED:
            return Response(
                {"detail": "이미 취소된 예약입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status", "updated_at"])

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_200_OK,
        )
