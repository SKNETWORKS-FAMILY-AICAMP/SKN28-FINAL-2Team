from __future__ import annotations
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    ROOT / 'src/rag/api.py',
    ROOT / 'src/rag/models.py',
    ROOT / 'src/rag/service.py',
    ROOT / 'backend/evaluation_app.py',
    ROOT / 'backend/services/evaluation_jobs.py',
    ROOT / 'evals/feature_backend/golden_cases.jsonl',
    ROOT / 'frontend/src/pages/EvaluationPage.jsx',
    ROOT / 'frontend/src/pages/evaluation/evaluation.module.css',
    ROOT / 'frontend/src/api/client.js',
    ROOT / 'scripts/windows/run_rag_backend.cmd',
]
missing = [str(p.relative_to(ROOT)) for p in REQUIRED if not p.exists()]
if missing:
    print('[ERROR] Missing evaluation files:')
    for item in missing:
        print(' -', item)
    raise SystemExit(1)
if importlib.util.find_spec('fastapi') is None or importlib.util.find_spec('uvicorn') is None:
    print('[ERROR] fastapi/uvicorn are not installed in the active environment.')
    raise SystemExit(1)
case_lines = [line for line in (ROOT/'evals/feature_backend/golden_cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')]
if not case_lines:
    print('[ERROR] Evaluation dataset is empty.')
    raise SystemExit(1)
print('feature/backend evaluation integration PASSED')
print(f'  Cases: {len(case_lines)}')
print('  RAG source: src/rag/api.py -> create_place_search_service()')
print('  Evaluation API: http://localhost:8001/docs')
print('  Evaluation UI:  http://localhost:5173/evaluation')
