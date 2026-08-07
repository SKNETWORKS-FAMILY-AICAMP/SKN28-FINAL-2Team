from __future__ import annotations
import importlib
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]

def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)

def main() -> int:
    env = ROOT / ".env"
    front_env = ROOT / "frontend" / ".env"
    if not env.exists(): fail(".env is missing. Copy .env.example to .env and fill the values.")
    if not front_env.exists(): fail("frontend/.env is missing. Copy frontend/.env.example to frontend/.env.")
    # Load project env without printing secrets.
    from dotenv import load_dotenv
    load_dotenv(env, override=True)
    needed = ["MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE", "ACCOUNT_DB_NAME", "TRAVEL_DB_NAME", "OPENAI_API_KEY"]
    missing = [key for key in needed if not os.getenv(key, "").strip()]
    if missing: fail("Missing environment values: " + ", ".join(missing) + ". If MYSQL_PASSWORD is not initialized, run BOOTSTRAP_MYSQL.cmd first.")
    vector_db = ROOT / os.getenv("CHROMA_PERSIST_DIRECTORY", "data/vectorstore") / "chroma.sqlite3"
    if os.getenv("CHROMA_MODE", "persistent").lower() == "persistent" and not vector_db.exists():
        fail("ChromaDB index is missing: data/vectorstore/chroma.sqlite3")
    modules = ["django", "rest_framework", "drf_spectacular", "corsheaders", "MySQLdb", "chromadb", "mysql.connector", "google.auth"]
    bad=[]
    for name in modules:
        try: importlib.import_module(name)
        except Exception as exc: bad.append(f"{name} ({exc})")
    if bad: fail("Python dependencies missing: " + "; ".join(bad))
    print("Tamna Plan preflight PASSED")
    print("  Backend base: uploaded origin/feature/backend @ 4339a9e")
    print("  RAG: feature/backend src/rag")
    print("  Frontend: http://localhost:5173")
    print("  Django: http://localhost:8000")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
