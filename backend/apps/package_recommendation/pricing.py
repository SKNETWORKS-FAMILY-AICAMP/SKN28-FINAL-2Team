"""Simple estimated pricing for a confirmed itinerary package."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


CUSTOM_PACKAGE_PREMIUM_RATE = 0.12
PRICE_ROUNDING_UNIT = 1_000
PRICING_VERSION = "2.0"


@dataclass(frozen=True)
class CustomPackagePrice:
    """Per-person estimated price based on a comparable stored package."""

    reference_package_price: int
    customization_fee: int
    price_per_person: int
    pricing_version: str = PRICING_VERSION

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)


def calculate_custom_package_price(reference_package_price: int) -> CustomPackagePrice:
    """Add a 12% premium to a comparable package's per-person price."""

    _validate_price(reference_package_price, "reference_package_price")

    price_per_person = _round_price(
        reference_package_price * (1 + CUSTOM_PACKAGE_PREMIUM_RATE)
    )
    return CustomPackagePrice(
        reference_package_price=reference_package_price,
        customization_fee=price_per_person - reference_package_price,
        price_per_person=price_per_person,
    )


def choose_reference_package_price(
    recommended_package_price: int | None,
    same_duration_package_prices: Iterable[int] = (),
) -> int:
    """Choose the recommendation price, or the same-duration average as fallback."""

    if recommended_package_price is not None:
        _validate_price(recommended_package_price, "recommended_package_price")
        return recommended_package_price

    prices = list(same_duration_package_prices)
    if not prices:
        raise ValueError("a recommended package price or fallback prices are required")
    for price in prices:
        _validate_price(price, "same_duration_package_price")
    return _round_price(sum(prices) / len(prices))


def _validate_price(price: int, field_name: str) -> None:
    if isinstance(price, bool) or not isinstance(price, int):
        raise TypeError(f"{field_name} must be an integer")
    if price <= 0:
        raise ValueError(f"{field_name} must be greater than zero")


def _round_price(amount: float) -> int:
    return round(amount / PRICE_ROUNDING_UNIT) * PRICE_ROUNDING_UNIT
