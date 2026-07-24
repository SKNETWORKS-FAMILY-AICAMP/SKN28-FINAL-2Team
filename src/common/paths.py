from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

DATA_ROOT = REPOSITORY_ROOT / "data"
RAW_DATA_ROOT = DATA_ROOT / "raw"
PROCESSED_DATA_ROOT = DATA_ROOT / "processed"
VECTORSTORE_ROOT = DATA_ROOT / "vectorstore"

SRC_ROOT = REPOSITORY_ROOT / "src"
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"

# Compatibility roots used by the pipeline entry points.
TOURAPI_DATA_ROOT = DATA_ROOT
TOURAPI_DATABASE_ROOT = SRC_ROOT / "storage" / "sql"
TOURAPI_SCRIPTS_ROOT = SRC_ROOT / "tourapi"

AIHUB_DATA_ROOT = DATA_ROOT
AIHUB_DATABASE_ROOT = SRC_ROOT / "aihub"
AIHUB_SCRIPTS_ROOT = SRC_ROOT / "aihub"
AIHUB_EXPORT_ROOT = PROCESSED_DATA_ROOT / "aihub" / "exports"
