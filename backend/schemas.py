from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class EvaluationRunRequest(BaseModel):
    case_ids: list[str] = Field(default_factory=list)
    max_cases: int | None = Field(default=None, ge=1, le=100)
    repeat: int = Field(default=1, ge=1, le=10)
    llm_judge: bool = False
    judge_model: str | None = None
    pass_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    case_score: float = Field(default=0.8, ge=0.0, le=1.0)
    include_results: bool = True

    @field_validator("case_ids")
    @classmethod
    def normalize_case_ids(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        return list(dict.fromkeys(normalized))
