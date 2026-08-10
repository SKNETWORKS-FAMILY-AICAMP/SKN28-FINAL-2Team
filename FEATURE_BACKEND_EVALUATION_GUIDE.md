# feature/backend RAG 평가 통합

이 평가 기능은 `sim/merge-all` RAG를 사용하지 않습니다.
현재 프로젝트가 실제 사용하는 `src.rag.api.create_place_search_service()`와 `PlaceSearchService.search_places()`를 직접 호출합니다.

## 실행

`START_TAMNA_PLAN.cmd` 실행 후:

- 서비스: http://localhost:5173/
- 평가 화면: http://localhost:5173/evaluation
- Django: http://localhost:8000/swagger/
- 평가 FastAPI: http://localhost:8001/docs

## 평가 케이스

`evals/feature_backend/golden_cases.jsonl`에 정의되어 있습니다.
기본 케이스는 한라수목원, 섭지코지, 음식점 필터, 숙박 필터, 자연 관광지 검색입니다.

## 평가 지표

- execution_success
- min_results
- required_place_recall (케이스에 필수 장소가 있을 때)
- content_type_filter_compliance (필터 케이스)
- unique_place_ratio
- mysql_grounding
- similarity_score_coverage
- rank_order_accuracy
- latency_within_limit

필수 게이트 지표가 실패하거나 케이스 평균 점수가 기본 0.8 미만이면 해당 케이스는 FAIL입니다.
전체 통과율 기본 기준은 0.8입니다.

## 결과 파일

`artifacts/rag_evaluation/api_jobs/<job-id>/` 아래 JSON과 Markdown으로 저장합니다.

## 환경변수

`frontend/.env`에 다음을 추가합니다.

```dotenv
VITE_RAG_API_BASE_URL=http://localhost:8001
```

백엔드 평가기는 프로젝트 루트 `.env`의 기존 MySQL, OpenAI, ChromaDB 설정을 그대로 사용합니다.
