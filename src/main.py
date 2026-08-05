from pathlib import Path

from src.engine import ItineraryEngine, create_container


PROJECT_ROOT = Path(__file__).resolve().parent.parent


container = create_container(
    project_root=PROJECT_ROOT,
)


retrieval_service = container.retrieval_service
place_search_service = retrieval_service
pattern_service = container.pattern_service
llm_service = container.llm_service

# Full pipeline: user input -> TravelCondition -> AIHub structure -> RAG
# -> Planner -> LLM itinerary (create_itinerary), and free-chat edits
# (update_itinerary_from_chat). See src/engine.py.
itinerary_engine = ItineraryEngine(container)
