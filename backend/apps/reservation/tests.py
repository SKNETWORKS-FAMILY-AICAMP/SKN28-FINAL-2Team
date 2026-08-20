from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.travel.models import Itinerary
from apps.travel.serializers import PackageSerializer

from .models import CartItem
from .serializers import ReservationCreateSerializer, ReservationItemSerializer
from .views import CartAPIView, create_package_itinerary


class ReservationItemSerializerTests(SimpleTestCase):
    def test_custom_itinerary_uses_current_title_and_first_thumbnail(self):
        items = Mock()
        items.exclude.return_value.exclude.return_value.exclude.return_value.order_by.return_value.first.return_value = SimpleNamespace(
            thumbnail="https://example.com/jeju.jpg"
        )
        day = SimpleNamespace(items=items)
        days = Mock()
        days.all.return_value.order_by.return_value = [day]
        itinerary = SimpleNamespace(title="현재 일정 이름", days=days)
        item = SimpleNamespace(
            product_type=CartItem.ProductType.CUSTOM_ITINERARY,
            package_db_id=None,
            package_id="CUSTOM-1",
            name="예약 당시 이름",
            reservation=SimpleNamespace(itinerary=itinerary),
        )
        serializer = ReservationItemSerializer()

        self.assertEqual(serializer.get_display_name(item), "현재 일정 이름")
        self.assertEqual(
            serializer.get_thumbnail_url(item),
            "https://example.com/jeju.jpg",
        )

    def test_stored_package_uses_current_catalog_name_and_thumbnail(self):
        item = SimpleNamespace(
            product_type=CartItem.ProductType.STORED_PACKAGE,
            package_db_id=10,
            package_id="PKG-10",
            name="예약 당시 이름",
        )
        package = SimpleNamespace(title="현재 패키지 이름")
        serializer = ReservationItemSerializer()

        with (
            patch.object(
                serializer,
                "_get_stored_package",
                return_value=package,
            ),
            patch.object(
                PackageSerializer,
                "get_thumbnail_url",
                return_value="https://example.com/package.jpg",
            ),
        ):
            self.assertEqual(
                serializer.get_display_name(item),
                "현재 패키지 이름",
            )
            self.assertEqual(
                serializer.get_thumbnail_url(item),
                "https://example.com/package.jpg",
            )


class CartAPIViewTests(SimpleTestCase):
    @patch("apps.reservation.views.CartItemSerializer")
    @patch("apps.reservation.views.CartItem.objects.get_or_create")
    @patch("apps.reservation.views.get_object_or_404")
    @patch("apps.reservation.views.CartItemCreateSerializer")
    def test_existing_catalog_item_is_linked_to_generated_itinerary(
        self,
        mocked_create_serializer,
        mocked_get_object,
        mocked_get_or_create,
        mocked_item_serializer,
    ):
        serializer = mocked_create_serializer.return_value
        serializer.validated_data = {
            "product_type": CartItem.ProductType.STORED_PACKAGE,
            "package_id": 10,
            "itinerary_id": 5,
        }
        itinerary = SimpleNamespace(
            id=5,
            status=Itinerary.Status.CONFIRMED,
            start_date=date(2026, 8, 20),
        )
        package = SimpleNamespace(
            id=10,
            title="현재 패키지 이름",
            estimated_price=80000,
        )
        mocked_get_object.side_effect = [itinerary, package]
        cart_item = SimpleNamespace(
            itinerary_id=None,
            itinerary=None,
            product_name="현재 패키지 이름",
            unit_price=80000,
            option_date=None,
            save=Mock(),
        )
        mocked_get_or_create.return_value = (cart_item, False)
        mocked_item_serializer.return_value.data = {"id": 1}
        request = APIRequestFactory().post(
            "/api/cart/",
            {
                "product_type": CartItem.ProductType.STORED_PACKAGE,
                "package_id": 10,
                "itinerary_id": 5,
            },
            format="json",
        )
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True),
        )

        response = CartAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertIs(cart_item.itinerary, itinerary)
        self.assertEqual(cart_item.option_date, itinerary.start_date)
        cart_item.save.assert_called_once_with(
            update_fields=[
                "itinerary",
                "product_name",
                "unit_price",
                "option_date",
            ]
        )


class ReservationCreateSerializerTests(SimpleTestCase):
    def test_accepts_package_start_date_and_people_count(self):
        serializer = ReservationCreateSerializer(
            data={
                "package_ids": [10],
                "start_date": "2026-08-21",
                "people_count": 3,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["start_date"], date(2026, 8, 21))
        self.assertEqual(serializer.validated_data["people_count"], 3)


class PackageItineraryCreationTests(SimpleTestCase):
    @patch("apps.reservation.views.ItineraryItem.objects.create")
    @patch("apps.reservation.views.ItineraryDay.objects.create")
    @patch("apps.reservation.views.Itinerary.objects.create")
    @patch("apps.reservation.views.PackageSerializer")
    def test_creates_package_itinerary_with_selected_date_and_people(
        self,
        mocked_package_serializer,
        mocked_itinerary_create,
        mocked_day_create,
        mocked_item_create,
    ):
        mocked_package_serializer.return_value.data = {
            "thumbnail_url": "https://example.com/package.jpg",
            "accommodation": {
                "title": "Test hotel",
                "address": "Jeju-si",
                "latitude": 33.123456,
                "longitude": 126.123456,
            },
            "course": [
                {
                    "day": 1,
                    "items": [
                        {
                            "sequence": 1,
                            "item_type": "tourism",
                            "latitude": Decimal("33.453285210694"),
                            "longitude": Decimal("126.587420689818"),
                            "title": "성산일출봉",
                        }
                    ],
                },
            ],
        }
        itinerary = SimpleNamespace()
        mocked_itinerary_create.return_value = itinerary
        mocked_day_create.return_value = SimpleNamespace()
        package = SimpleNamespace(id=10, title="제주 패키지", duration_days=2)

        result = create_package_itinerary(
            SimpleNamespace(),
            package,
            date(2026, 8, 21),
            3,
            duration_days=3,
        )

        self.assertIs(result, itinerary)
        self.assertEqual(
            mocked_itinerary_create.call_args.kwargs["start_date"],
            date(2026, 8, 21),
        )
        self.assertEqual(
            mocked_itinerary_create.call_args.kwargs["end_date"],
            date(2026, 8, 23),
        )
        self.assertEqual(
            mocked_itinerary_create.call_args.kwargs["companion_count"],
            3,
        )
        self.assertEqual(mocked_day_create.call_count, 3)
        self.assertEqual(mocked_item_create.call_count, 1)
        self.assertEqual(
            mocked_itinerary_create.call_args.kwargs["engine_state"],
            {
                "itinerary": {
                    "package_db_id": 10,
                    "hotel": {
                        "title": "Test hotel",
                        "address": "Jeju-si",
                        "latitude": 33.123456,
                        "longitude": 126.123456,
                        "nights": 2,
                    },
                }
            },
        )
        self.assertEqual(
            mocked_item_create.call_args_list[0].kwargs["latitude"],
            Decimal("33.453285"),
        )
        self.assertEqual(
            mocked_item_create.call_args_list[0].kwargs["longitude"],
            Decimal("126.587421"),
        )
