# Project ownership and integration boundaries

## LLM/RAG work

When a task concerns LLM prompting, retrieval, AIHub route patterns, TourAPI
candidate selection, itinerary generation, or RAG evaluation:

- Treat `backend/` as read-only. It is owned and implemented by another team
  member.
- Do not add, edit, move, or delete files under `backend/`.
- Do not connect `src/rag` to Django, Django REST Framework, FastAPI, or any
  other HTTP framework.
- Do not add RAG imports, views, serializers, URLs, migrations, settings, or
  dependencies to `backend/`.
- Keep the RAG implementation framework-independent under `src/rag/`.
- Put RAG tests under `tests/rag/`.
- Expose only a plain Python contract from `src/rag`; the backend owner will
  build the HTTP/API adapter separately.
- If backend integration is needed, document the expected request and response
  contract without implementing it in `backend/`.

The automated ownership check is:

```powershell
python -m pytest tests/rag/test_ownership_boundary.py
```

This boundary may be changed only when the user explicitly authorizes backend
integration work.
