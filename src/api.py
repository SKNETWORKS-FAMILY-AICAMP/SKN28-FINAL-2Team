from pathlib import Path
from typing import Any, Callable

from src.engine import ItineraryEngine, create_container

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_container = None


def get_container():
    global _container
    if _container is None:
        _container = create_container(project_root=PROJECT_ROOT)
    return _container


class _LazyProxy:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory

    def __getattr__(self, name: str) -> Any:
        return getattr(self._factory(), name)


class _LazyItineraryEngine:
    def create_itinerary(self, user_text: str):
        return ItineraryEngine(get_container()).create_itinerary(user_text)

    def update_itinerary_from_chat(self, state, user_text: str):
        return ItineraryEngine(get_container()).update_itinerary_from_chat(
            state,
            user_text,
        )


container = _LazyProxy(get_container)
retrieval_service = _LazyProxy(lambda: get_container().retrieval_service)
pattern_service = _LazyProxy(lambda: get_container().pattern_service)
llm_service = _LazyProxy(lambda: get_container().llm_service)
itinerary_engine = _LazyItineraryEngine()
