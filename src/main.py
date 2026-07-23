from pathlib import Path

from src.engine import create_container


PROJECT_ROOT = Path(__file__).resolve().parent.parent


container = create_container(
    project_root=PROJECT_ROOT,
)


retrieval_service = container.retrieval_service
pattern_service = container.pattern_service