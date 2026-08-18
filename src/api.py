from functools import cache
from pathlib import Path

from src.engine import ItineraryEngine, create_container

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@cache
def get_itinerary_engine() -> ItineraryEngine:
    container = create_container(project_root=PROJECT_ROOT)
    return ItineraryEngine(container)
