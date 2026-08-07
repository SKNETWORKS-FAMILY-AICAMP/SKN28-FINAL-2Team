# feature/backend runnable integration

## Authority / source
- Backend + RAG base: `origin/feature/backend` from the uploaded `feature_backend.zip`
- Base commit: `4339a9e8688992ab092ea83bc519fc55d8bf23ea`
- `src/rag` was not replaced with the sim/merge-all implementation.

## Runtime-only/support additions imported from the previous local integration
- Existing 2,102-document persistent ChromaDB index (the JSON dataset is structurally identical)
- Curated 30-package dataset, schema, and loader
- Windows one-click launcher/preflight helpers
- Kakao JavaScript SDK loading and env-based Kakao Maps key
- Django/MySQL bootstrap fixes and mysqlclient runtime dependency
- Cross-database selected-package FK correction (Django cannot enforce FKs across accounts_db -> travel DB)
- Lazy itinerary-engine import so login/Swagger can start even before the RAG runtime is first used

## First local run
1. Copy `.env.example` to `.env`, fill MySQL/OpenAI/OAuth values.
2. Copy `frontend/.env.example` to `frontend/.env`, fill Google/Kakao frontend keys.
3. Ensure MySQL is running. If `tour_app` does not have both DB permissions, set MYSQL_ADMIN_* temporarily and run:
   `python scripts/bootstrap_mysql.py --env-file .env`
4. If travel tables are not loaded, after the venv exists run `scripts\windows\setup_data.cmd`.
5. Run `START_TAMNA_PLAN.cmd`.

Frontend: http://localhost:5173/
Django Swagger: http://localhost:8000/swagger/

## Validation note
- The supplied branch's AIHub unit-test fixture predates the required `TravelCondition.companion_count` field; production code was not rolled back merely to satisfy that stale fixture.
- The original vectorstore manifest was stale (`places-v4`, 1,866) while the supplied JSON is `places-v5`, 2,102. The integrated runtime manifest is corrected to the actual 2,102-document index.

## Convenience helpers
- `BOOTSTRAP_MYSQL.cmd`: creates/grants `accounts_db` + travel DB using temporary MySQL admin credentials.
- `SETUP_TRAVEL_DATA.cmd`: loads TourAPI + AIHub + the curated 30-package dataset.
