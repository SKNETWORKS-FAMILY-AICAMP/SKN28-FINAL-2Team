"""Accommodation-only pricing for a confirmed custom itinerary."""

from __future__ import annotations

from dataclasses import asdict, dataclass


PRICING_VERSION = "3.0"
ROOM_OCCUPANCY = 2
STANDARD_ROOM_PRICE = 140_000
UPPER_ROOM_PRICE = 220_000
LUXURY_ROOM_PRICE = 350_000

LUXURY_HOTEL_WORDS = ("JW 메리어트", "제주신라호텔", "파르나스 호텔")
UPPER_HOTEL_WORDS = (
    "디아넥스",
    "라온호텔",
    "라헨느",
    "루체빌",
    "에코랜드 호텔",
    "엠버리조트",
    "제주 블랙스톤",
    "제주신화월드",
)


@dataclass(frozen=True)
class CustomPackagePrice:
    """Per-person price for the lodging included in a custom itinerary."""

    nights: int
    lodging_name: str | None
    lodging_tier: str | None
    room_price_per_night: int
    price_per_person: int
    pricing_basis: str
    pricing_version: str = PRICING_VERSION

    def to_dict(self) -> dict[str, int | str | None]:
        return asdict(self)


def calculate_custom_package_price(
    nights: int,
    lodging_name: str | None = None,
) -> CustomPackagePrice:
    """Return zero for a day trip, otherwise charge only estimated lodging."""

    _validate_nights(nights)
    normalized_name = (lodging_name or "").strip() or None

    if nights == 0:
        return CustomPackagePrice(
            nights=0,
            lodging_name=None,
            lodging_tier=None,
            room_price_per_night=0,
            price_per_person=0,
            pricing_basis="free_day_trip",
        )

    room_price, lodging_tier = estimate_room_price(normalized_name)
    return CustomPackagePrice(
        nights=nights,
        lodging_name=normalized_name,
        lodging_tier=lodging_tier,
        room_price_per_night=room_price,
        price_per_person=room_price * nights // ROOM_OCCUPANCY,
        pricing_basis="estimated_accommodation_only",
    )


def estimate_room_price(lodging_name: str | None) -> tuple[int, str]:
    """Use the same lodging tiers as the stored-package generation script."""

    name = lodging_name or ""
    if any(word.casefold() in name.casefold() for word in LUXURY_HOTEL_WORDS):
        return LUXURY_ROOM_PRICE, "luxury"
    if any(word.casefold() in name.casefold() for word in UPPER_HOTEL_WORDS):
        return UPPER_ROOM_PRICE, "upper"
    return STANDARD_ROOM_PRICE, "standard"


def _validate_nights(nights: int) -> None:
    if isinstance(nights, bool) or not isinstance(nights, int):
        raise TypeError("nights must be an integer")
    if nights < 0:
        raise ValueError("nights must be zero or greater")
