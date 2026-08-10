from __future__ import annotations


_COMPANION_PARTY_TYPES = {
    "solo": {"solo"},
    "friend": {"non_family_two", "non_family_group"},
    "couple": {"non_family_two"},
    "family": {
        "family_two",
        "family_group",
        "with_children",
        "with_parents",
        "three_generations",
    },
}


def split_csv(value: str | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            item.strip().lower()
            for item in str(value or "").split(",")
            if item.strip()
        )
    )


def build_match_profile(companion: str | None, tags: str | None) -> dict[str, list[str]]:
    party_types: set[str] = set()
    for value in split_csv(companion):
        party_types.update(_COMPANION_PARTY_TYPES.get(value, ()))
    return {
        "party_types": sorted(party_types),
        "themes": list(split_csv(tags)),
        "paces": [],
    }


def infer_package_style(companion: str | None, tags: str | None) -> str:
    companions = set(split_csv(companion))
    package_tags = set(split_csv(tags))
    if "family" in companions:
        return "family"
    if "experience" in package_tags:
        return "activity"
    if "nature" in package_tags:
        return "healing"
    return ""
