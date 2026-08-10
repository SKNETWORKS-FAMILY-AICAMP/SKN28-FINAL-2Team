Tamna Plan feature/backend RAG evaluation patch

Base expected:
- feature_backend_mysql_tuning_integrated
- active RAG: src/rag/api.py, models.py, service.py from feature/backend

Apply:
1. Stop Tamna Plan servers.
2. Copy this patch's contents into the project root and overwrite matching files.
3. Keep your existing .env and frontend/.env.
4. Add/confirm in frontend/.env:
   VITE_RAG_API_BASE_URL=http://localhost:8001
5. Run START_TAMNA_PLAN.cmd.
6. Open http://localhost:5173/evaluation

This patch does NOT replace files under src/rag/.
