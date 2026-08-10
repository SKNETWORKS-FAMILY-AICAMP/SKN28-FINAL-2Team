

## MySQL tuning toolkit

정형 DB 구조/성능 분석은 다음 명령으로 실행할 수 있습니다.

```cmd
python -m scripts.storage.analyze_mysql_tuning report
```

상세 설명은 `docs/MYSQL_TUNING_GUIDE.md`를 참고하세요. 기본 리포트는 읽기 전용이며 자동으로 인덱스를 생성하거나 삭제하지 않습니다.

## feature/backend RAG evaluation

`START_TAMNA_PLAN.cmd` now starts three local processes:

- React/Vite: `http://localhost:5173/`
- Django business API: `http://localhost:8000/`
- feature/backend RAG evaluation FastAPI: `http://localhost:8001/`

Open the evaluation dashboard at `http://localhost:5173/evaluation`.
The evaluator calls the active `src.rag.api.create_place_search_service()` directly; it does not import the old sim/merge-all RAG.
See `FEATURE_BACKEND_EVALUATION_GUIDE.md` for details.
