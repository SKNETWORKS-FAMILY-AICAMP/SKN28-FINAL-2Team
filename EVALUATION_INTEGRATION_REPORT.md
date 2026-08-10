# Evaluation integration report

Base: latest feature/backend runnable + MySQL exporter/tuning integration.

Added only evaluation adapter/UI around the active feature/backend RAG.
The files under `src/rag/` are not replaced or modified by this integration.

Added:
- `backend/evaluation_app.py`
- `backend/services/evaluation_jobs.py`
- `backend/json_utils.py`
- `backend/schemas.py`
- `evals/feature_backend/golden_cases.jsonl`
- `frontend/src/pages/EvaluationPage.jsx`
- `frontend/src/pages/evaluation/evaluation.module.css`
- `frontend/src/api/client.js`
- `/evaluation` route and navigation link
- FastAPI/uvicorn requirements
- evaluation launcher on port 8001
