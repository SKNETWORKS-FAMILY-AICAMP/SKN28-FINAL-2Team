"""Strict JSON Schemas used by OpenAI structured outputs."""

from __future__ import annotations


CONDITION_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "region": {"type": ["string", "null"]},
        "start_date": {
            "type": ["string", "null"],
            "pattern": r"^\d{4}-\d{2}-\d{2}$",
        },
        "end_date": {
            "type": ["string", "null"],
            "pattern": r"^\d{4}-\d{2}-\d{2}$",
        },
        "duration_days": {
            "type": ["integer", "null"],
            "minimum": 1,
            "maximum": 30,
        },
        "party_type": {
            "type": ["string", "null"],
            "enum": [
                "solo",
                "non_family_two",
                "non_family_group",
                "family_two",
                "family_group",
                "with_children",
                "with_parents",
                "three_generations",
                None,
            ],
        },
        "local_transport": {
            "type": ["string", "null"],
            "enum": [
                "rental_car",
                "own_car",
                "public_transit",
                "taxi",
                "mixed",
                None,
            ],
        },
        "preferred_visit_types": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "nature",
                    "history",
                    "culture",
                    "market_shopping",
                    "leisure",
                    "theme_park",
                    "trail",
                    "festival",
                    "food_cafe",
                    "experience",
                ],
            },
        },
        "companion_count": {"type": ["integer", "null"], "minimum": 0},
        "purpose_codes": {"type": "array", "items": {"type": "string"}},
        "pace": {
            "type": ["string", "null"],
            "enum": ["relaxed", "balanced", "packed", None],
        },
        "arrival_time": {
            "type": ["string", "null"],
            "pattern": r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        },
        "departure_time": {
            "type": ["string", "null"],
            "pattern": r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        },
        "entry_point": {"type": ["string", "null"]},
        "exit_point": {"type": ["string", "null"]},
        "accommodation_address": {"type": ["string", "null"]},
        "preferred_places": {"type": "array", "items": {"type": "string"}},
        "preferred_foods": {"type": "array", "items": {"type": "string"}},
        "include_breakfast": {"type": ["boolean", "null"]},
        "meal_search_radius_km": {
            "type": ["number", "null"],
            "minimum": 1,
            "maximum": 30,
        },
        "skipped_meals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "day": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30,
                    },
                    "meal_type": {
                        "type": "string",
                        "enum": ["breakfast", "lunch", "dinner"],
                    },
                },
                "required": ["day", "meal_type"],
            },
        },
        "travel_styles": {"type": "array", "items": {"type": "string"}},
        "must_visit_places": {"type": "array", "items": {"type": "string"}},
        "required_day_itineraries": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "day": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30,
                    },
                    "place_names": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["day", "place_names"],
            },
        },
        "excluded_places": {"type": "array", "items": {"type": "string"}},
        "excluded_foods": {"type": "array", "items": {"type": "string"}},
        "avoid_long_distance": {"type": ["boolean", "null"]},
        "opening_hours_constraints": {
            "type": "array",
            "items": {"type": "string"},
        },
        "parking_required": {"type": ["boolean", "null"]},
        "indoor_preference": {
            "type": ["string", "null"],
            "enum": ["indoor", "outdoor", "either", None],
        },
        "budget_per_person": {"type": ["integer", "null"], "minimum": 0},
        "mobility_constraints": {
            "type": "array",
            "items": {"type": "string"},
        },
        "explicit_fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "region",
        "start_date",
        "end_date",
        "duration_days",
        "party_type",
        "local_transport",
        "preferred_visit_types",
        "companion_count",
        "purpose_codes",
        "pace",
        "arrival_time",
        "departure_time",
        "entry_point",
        "exit_point",
        "accommodation_address",
        "preferred_places",
        "preferred_foods",
        "include_breakfast",
        "meal_search_radius_km",
        "skipped_meals",
        "travel_styles",
        "must_visit_places",
        "required_day_itineraries",
        "excluded_places",
        "excluded_foods",
        "avoid_long_distance",
        "opening_hours_constraints",
        "parking_required",
        "indoor_preference",
        "budget_per_person",
        "mobility_constraints",
        "explicit_fields",
    ],
}


ITINERARY_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "choices": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "day": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30,
                    },
                    "slot_sequence": {"type": "integer", "minimum": 1},
                    "content_id": {"type": "integer", "minimum": 1},
                    "stay_minutes": {
                        "type": "integer",
                        "minimum": 20,
                        "maximum": 360,
                    },
                    "reason": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 300,
                    },
                },
                "required": [
                    "day",
                    "slot_sequence",
                    "content_id",
                    "stay_minutes",
                    "reason",
                ],
            },
        }
    },
    "required": ["choices"],
}
