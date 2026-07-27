# RAG ownership boundary

`src/rag` is a framework-independent Python package. It owns:

- travel-condition extraction prompts and structured output schemas;
- missing-condition clarification;
- AIHub route-pattern retrieval;
- TourAPI vector retrieval and candidate scoring;
- whitelist enforcement;
- itinerary generation, validation, and repair;
- orchestration and RAG evaluation logic.

It does not own:

- Django/FastAPI views, URLs, serializers, authentication, or sessions;
- backend database models or migrations;
- HTTP request/response handling;
- frontend rendering.

The package may define plain Python inputs and outputs for a future adapter, but
the backend team is responsible for importing and exposing that contract.

Until the user explicitly authorizes integration, neither direction may import
the other:

```text
src/rag  -X->  backend
backend  -X->  src/rag
```

Run `python -m pytest tests/rag/test_ownership_boundary.py` to verify the
boundary.
