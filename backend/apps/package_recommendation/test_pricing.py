from django.test import SimpleTestCase

from .pricing import (
    calculate_custom_package_price,
    choose_reference_package_price,
)


class CustomPackagePricingTests(SimpleTestCase):
    def test_adds_twelve_percent_to_recommended_package_price(self):
        result = calculate_custom_package_price(666_000)

        self.assertEqual(result.reference_package_price, 666_000)
        self.assertEqual(result.customization_fee, 80_000)
        self.assertEqual(result.price_per_person, 746_000)
        self.assertEqual(result.pricing_version, "2.0")

    def test_rounds_final_price_to_nearest_thousand_won(self):
        result = calculate_custom_package_price(333_000)

        self.assertEqual(result.price_per_person, 373_000)
        self.assertEqual(result.customization_fee, 40_000)

    def test_returns_serializable_breakdown(self):
        result = calculate_custom_package_price(500_000).to_dict()

        self.assertEqual(
            result,
            {
                "reference_package_price": 500_000,
                "customization_fee": 60_000,
                "price_per_person": 560_000,
                "pricing_version": "2.0",
            },
        )

    def test_prefers_recommended_package_price(self):
        reference_price = choose_reference_package_price(
            666_000,
            [400_000, 500_000],
        )

        self.assertEqual(reference_price, 666_000)

    def test_uses_same_duration_average_when_recommendation_is_missing(self):
        reference_price = choose_reference_package_price(
            None,
            [400_000, 500_000, 600_000],
        )

        self.assertEqual(reference_price, 500_000)

    def test_rejects_missing_or_invalid_reference_prices(self):
        with self.assertRaises(ValueError):
            choose_reference_package_price(None, [])
        with self.assertRaises(ValueError):
            calculate_custom_package_price(0)
        with self.assertRaises(TypeError):
            calculate_custom_package_price(100_000.0)
