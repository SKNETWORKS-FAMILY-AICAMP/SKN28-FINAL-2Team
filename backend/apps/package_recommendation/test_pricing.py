from django.test import SimpleTestCase

from .pricing import calculate_custom_package_price


class CustomPackagePricingTests(SimpleTestCase):
    def test_day_trip_is_free(self):
        result = calculate_custom_package_price(0)

        self.assertEqual(result.price_per_person, 0)
        self.assertEqual(result.pricing_basis, "free_day_trip")
        self.assertEqual(result.room_price_per_night, 0)

    def test_standard_lodging_price_is_split_between_two_people(self):
        result = calculate_custom_package_price(2, "라벤더리조트")

        self.assertEqual(result.lodging_tier, "standard")
        self.assertEqual(result.room_price_per_night, 140_000)
        self.assertEqual(result.price_per_person, 140_000)

    def test_upper_and_luxury_lodging_names_use_existing_tiers(self):
        upper = calculate_custom_package_price(1, "엠버리조트")
        luxury = calculate_custom_package_price(1, "제주신라호텔")

        self.assertEqual(upper.price_per_person, 110_000)
        self.assertEqual(luxury.price_per_person, 175_000)

    def test_returns_serializable_breakdown(self):
        result = calculate_custom_package_price(1, "일반 숙소").to_dict()

        self.assertEqual(
            result,
            {
                "nights": 1,
                "lodging_name": "일반 숙소",
                "lodging_tier": "standard",
                "room_price_per_night": 140_000,
                "price_per_person": 70_000,
                "pricing_basis": "estimated_accommodation_only",
                "pricing_version": "3.0",
            },
        )

    def test_rejects_invalid_nights(self):
        with self.assertRaises(ValueError):
            calculate_custom_package_price(-1)
        with self.assertRaises(TypeError):
            calculate_custom_package_price(1.0)
