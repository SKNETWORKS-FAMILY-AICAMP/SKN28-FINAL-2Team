from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re
from typing import Any, Mapping


JEJU_LONGITUDE_RANGE = (125.0, 127.5)
JEJU_LATITUDE_RANGE = (32.5, 34.0)
CITY_PATTERN = re.compile(r"(제주시|서귀포시)")
DISTRICT_PATTERN = re.compile(r"([가-힣0-9]+(?:읍|면|동))")
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


class _TextExtractor(HTMLParser):
    BLOCK_TAGS = {"br", "div", "li", "p", "section", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    parser = _TextExtractor()
    parser.feed(unescape(str(value)))
    parser.close()
    return " ".join("".join(parser.parts).split())


def extract_first_url(value: Any) -> str:
    if value in (None, ""):
        return ""
    match = URL_PATTERN.search(unescape(str(value)))
    return match.group(0).rstrip(".,);") if match else ""


def first_value(record: Mapping[str, Any], *fields: str) -> str:
    for field in fields:
        value = record.get(field)
        if value not in (None, "") and str(value).strip():
            return str(value).strip()
    return ""


def parse_address(address: str) -> tuple[str, str]:
    city_match = CITY_PATTERN.search(address)
    city = city_match.group(1) if city_match else ""
    tail = address[city_match.end() :] if city_match else address
    district_match = DISTRICT_PATTERN.search(tail)
    district = district_match.group(1) if district_match else ""
    return city, district


def validated_coordinates(longitude: str, latitude: str) -> tuple[float | None, float | None]:
    try:
        parsed_longitude = float(longitude)
        parsed_latitude = float(latitude)
    except (TypeError, ValueError):
        return None, None
    if not (
        JEJU_LONGITUDE_RANGE[0] <= parsed_longitude <= JEJU_LONGITUDE_RANGE[1]
        and JEJU_LATITUDE_RANGE[0] <= parsed_latitude <= JEJU_LATITUDE_RANGE[1]
    ):
        return None, None
    return parsed_longitude, parsed_latitude
