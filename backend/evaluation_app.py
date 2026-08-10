from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.json_utils import to_jsonable
from backend.schemas import EvaluationRunRequest
from backend.services import FeatureBackendEvaluationManager
from src.common.env import load_env_file


def _cors_origins() -> list[str]:
    configured = os.environ.get("EVALUATION_CORS_ORIGINS", "")
    if configured.strip():
        return [item.strip() for item in configured.split(",") if item.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]


def _rag_status(root: Path) -> dict[str, Any]:
    env_file = root / ".env"
    if env_file.exists():
        load_env_file(env_file)
    vectorstore = Path(os.environ.get("CHROMA_PERSIST_DIRECTORY", "data/vectorstore"))
    if not vectorstore.is_absolute():
        vectorstore = root / vectorstore
    files = [item for item in vectorstore.rglob("*") if item.is_file()] if vectorstore.exists() else []
    mysql = {
        key: bool(os.environ.get(key))
        for key in ("MYSQL_HOST", "MYSQL_USER", "MYSQL_DATABASE")
    }
    return {
        "source": "origin/feature/backend",
        "openai_api_key_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "mysql": mysql,
        "mysql_configured": all(mysql.values()),
        "chroma_collection": os.environ.get("CHROMA_COLLECTION", "jeju_places"),
        "vectorstore_path": str(vectorstore),
        "vectorstore_exists": vectorstore.exists(),
        "chroma_index_ready": bool(files),
        "chroma_file_count": len(files),
    }


def create_app(project_root: str | Path | None = None) -> FastAPI:
    root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    env_file = root / ".env"
    if env_file.exists():
        load_env_file(env_file)
    manager = FeatureBackendEvaluationManager(
        root,
        max_workers=int(os.environ.get("RAG_EVALUATION_MAX_WORKERS", "1")),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        manager.shutdown()

    app = FastAPI(
        title="탐나플랜 feature/backend RAG 평가 API",
        version="1.0.0",
        description=(
            "Evaluation-only FastAPI adapter for the feature/backend "
            "PlaceSearchService. It does not replace or import sim/merge-all RAG."
        ),
        lifespan=lifespan,
    )
    app.state.project_root = root
    app.state.evaluation_manager = manager
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "tamna-plan-feature-backend-rag-evaluation",
            "project_root": str(root),
            "rag": _rag_status(root),
            "evaluation_dataset_exists": manager.dataset_path.exists(),
        }

    @app.get("/api/evaluation/cases")
    def evaluation_cases() -> dict[str, Any]:
        try:
            cases = manager.list_cases()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"count": len(cases), "cases": to_jsonable(cases)}

    @app.post("/api/evaluation/run", status_code=status.HTTP_202_ACCEPTED)
    def evaluation_run(payload: EvaluationRunRequest) -> dict[str, Any]:
        try:
            job = manager.submit(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return job.to_dict()

    @app.get("/api/evaluation/jobs")
    def evaluation_jobs() -> dict[str, Any]:
        jobs = manager.list_jobs()
        return {"count": len(jobs), "jobs": jobs}

    @app.get("/api/evaluation/jobs/{job_id}")
    def evaluation_job(job_id: str) -> dict[str, Any]:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Evaluation job not found")
        return job.to_dict()

    @app.get("/api/evaluation/jobs/{job_id}/report")
    def evaluation_job_report(job_id: str) -> JSONResponse:
        try:
            artifact = manager.read_job_artifact(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Evaluation job not found") from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return JSONResponse(content=to_jsonable(artifact))

    @app.get("/api/evaluation/jobs/{job_id}/download/{file_format}")
    def evaluation_job_download(job_id: str, file_format: str) -> FileResponse:
        if file_format not in {"json", "md"}:
            raise HTTPException(status_code=400, detail="Format must be json or md")
        try:
            path = manager.job_file(job_id, file_format)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Evaluation job not found") from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        media_type = "application/json" if file_format == "json" else "text/markdown"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.get("/api/evaluation/reports")
    def evaluation_reports() -> dict[str, Any]:
        reports = manager.list_reports()
        return {"count": len(reports), "reports": reports}

    @app.get("/api/evaluation/report")
    def evaluation_report(path: str = Query(...)) -> JSONResponse:
        try:
            resolved = manager.resolve_report_path(path)
            artifact = json.loads(resolved.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Report not found") from exc
        return JSONResponse(content=to_jsonable(artifact))

    return app


app = create_app()
