# feature/backend 분석 및 기존 작업본 대조

## 기준
- 사용자 업로드: `feature_backend.zip`
- ZIP 내부 working tree는 `main`이었으나, 포함된 Git remote ref의 최신 `origin/feature/backend`를 기준으로 사용함.
- 기준 커밋: `4339a9e8688992ab092ea83bc519fc55d8bf23ea` (`fix: top-k 개수 수정`)
- RAG / Backend의 권위본(authority)은 위 커밋이며, 이전 `sim/merge-all` RAG는 사용하지 않음.

## 원본 feature/backend의 실행 판정
원본 브랜치는 코드 문법 자체는 정상이나, 새 PC에서 압축을 풀어 즉시 전체 기능을 실행하기에는 준비가 부족함.

주요 원인:
1. Django MySQL backend가 요구하는 `mysqlclient`가 requirements에 없음.
2. `data/vectorstore`에는 manifest만 있고 실제 persistent ChromaDB index가 없음.
3. `.env.example`이 Django DB / OAuth / CORS 실행에 필요한 값을 충분히 안내하지 않음.
4. bootstrap 스크립트가 `accounts_db` 생성/권한 부여를 하지 않아 Django migration에서 권한 오류가 날 수 있음.
5. `Itinerary.selected_package`가 accounts DB에서 travel DB의 unmanaged Package를 ForeignKey로 취급하여 cross-DB FK 구조가 불안정함.
6. travel service가 모듈 import 시점에 RAG engine을 생성하여, RAG 설정 문제 하나가 로그인/Swagger 등 Django 전체 시작을 막을 수 있음.
7. Kakao 로그인 코드는 JavaScript SDK를 기대하지만 원본 `frontend/index.html`에는 로그인 SDK가 없음.
8. 최신 package recommendation 코드는 `travel_packages`, `package_items` 데이터가 필요하지만 원본 ZIP에는 실제 30개 package dataset/loader가 없음.

## 기존 작업본(`sktteam2fb_0805_3`)과의 큰 차이

### 새 feature/backend가 더 최신인 부분
- package recommendation Django app이 추가됨.
- `src/recommender`의 package scoring/repository/service가 추가됨.
- itinerary migrations가 0011까지 진행됨.
- 채팅 기반 일정 생성 UX가 더 개선됨.
- 날짜 선택 캘린더와 채팅 상태 유지가 들어감.
- 일정 생성 이후 AI 추천 package 3개 노출 흐름이 추가됨.
- 비용/교통수단 등 불필요 필드가 최신 기획에 맞게 정리됨.
- 공통 frontend 파일 대부분이 기존 8/5 작업본 이후 다시 수정됨.

### 기존 작업본에만 있던 지원 요소
- 실제 ChromaDB persistent index.
- 검증된 30개 package dataset + MySQL loader/schema.
- Windows one-click launcher와 preflight.
- OAuth 실행 보조 설정/SDK.
- 이전 실험용 `/evaluation` UI 및 다른 RAG 평가기 흔적.

이 통합본은 마지막 항목(다른 RAG 평가기)은 가져오지 않고, 실행에 필요한 데이터/런처/OAuth/DB 보조만 선택적으로 가져옴.

## 이번 통합에서 feature/backend에 추가한 것
- `mysqlclient>=2.2.8,<3.0`.
- 실행 가능한 `.env.example`, `frontend/.env.example`.
- Kakao JavaScript SDK 및 env 기반 Kakao Maps app key.
- `accounts_db` + travel DB를 생성/권한 부여하는 bootstrap 개선.
- Django SECRET/CORS/CSRF/host 설정 env화.
- cross-DB package 선택값을 integer id로 분리하여 외부 DB FK를 피함.
- RAG engine lazy initialization: 로그인/Swagger/migrate는 RAG와 독립적으로 시작 가능.
- OAuth API base URL 일관화 및 Kakao email 미제공 대응.
- Windows `START_TAMNA_PLAN.cmd`, `STOP_TAMNA_PLAN.cmd`, preflight/setup helpers.
- 기존 2,102문서 ChromaDB persistent index.
- 검증된 30개 package dataset / schema / loader.

## RAG 보존 검증
다음 파일은 업로드된 최신 `origin/feature/backend`와 byte-identical임.
- `src/rag/__init__.py`
- `src/rag/api.py`
- `src/rag/models.py`
- `src/rag/service.py`

ChromaDB:
- collection: `jeju_places`
- dimension: 1536
- embedding count: 2,102
- preprocessing: `places-v5`
- embedding model metadata: `text-embedding-3-small`

## 정적 검증 결과
- Python `compileall`: PASS.
- RAG 4-file byte identity: PASS.
- package data validation: 30 packages / 415 items / 309 unique content IDs: PASS.
- ChromaDB SQLite collection/index presence: PASS (2,102 embeddings).
- React JSX parse / local relative import check: PASS.
- Git conflict marker scan: PASS.

## 현재 원본 테스트의 알려진 문제
`tests/aihub/test_aihub_similarity.py`는 최신 `TravelCondition`이 요구하는 `companion_count`를 아직 전달하지 않아 31개가 `TypeError`로 실패하고 2개가 통과함. 이는 최신 production model과 오래된 test fixture의 불일치이며, 런타임 RAG 코드를 이전 인터페이스로 되돌리지는 않았음.

## 로컬 실행
1. `.env.example` -> `.env`, 실제 MySQL/OpenAI/OAuth 값 입력.
2. `frontend/.env.example` -> `frontend/.env`, Google/Kakao frontend 값 입력.
3. MySQL 실행.
4. 필요 시 `python scripts/bootstrap_mysql.py --env-file .env`.
5. travel 데이터가 없다면 `scripts\\windows\\setup_data.cmd`.
6. `START_TAMNA_PLAN.cmd`.

- Frontend: `http://localhost:5173/`
- Django Swagger: `http://localhost:8000/swagger/`

## Convenience helpers
- `BOOTSTRAP_MYSQL.cmd`: creates/grants `accounts_db` + travel DB using temporary MySQL admin credentials.
- `SETUP_TRAVEL_DATA.cmd`: loads TourAPI + AIHub + the curated 30-package dataset.
