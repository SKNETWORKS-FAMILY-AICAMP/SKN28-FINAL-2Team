# 탐나플랜 Backend

요구사항 정의서(AI 여행 상품 추천) 중 **AI 기능(M003)과 관리자 기능(M002)을 제외**하고,
이미 만들어진 프론트엔드 5페이지 흐름(랜딩 → AI 대화 → 일정 편집 → 최종 검토 → 예약/결제)과
연관된 **사용자용 기능만** 우선순위 높은 것 위주로 구현했습니다.

RAG/AI는 이미 별도로 만들어져 있다는 전제 하에, 백엔드는 그 결과를 저장·조회·계산하는
역할만 담당합니다(AI 추천 로직 자체는 이 백엔드에 없습니다).

## 무엇을 만들었나 (요구사항 ID 매핑)

| 앱 | 구현 내용 | 관련 요구사항 |
|---|---|---|
| `accounts` (기존 + 확장) | 구글/카카오 소셜 로그인, JWT 로그아웃(블랙리스트), 내 정보 조회/수정 | M001-F-001, 002, 003 |
| `travel` (신규) | 관광지/숙소/맛집/패키지 목록·상세(+필터), 최종 일정표 CRUD, 일자별 일정, 직접 일정 추가, 예상 비용 계산, 경로 좌표, 일정 공유 | M002-F-001(조회만)·002·003, M004 전체, M005-F-003·004·005, M006-F-002~005 |
| `reservation` (신규) | 장바구니(담기/조회/삭제), 예약 요청(시연, 결제 연동 없음), 예약 내역 조회 | M005-F-007, 008, M001-F-006 |
| `bookmark` (기존 스캐폴드 구현) | 패키지 찜하기/찜 목록 조회/찜 해제 | M005-F-006, M001-F-005 |
| `history` (기존 스캐폴드 구현) | 이용 기록 로그 (조회/생성), `fake_data.json` 적재 커맨드 | (참고 데이터 기반, M006-F-008과 유사한 성격의 로그) |

**의도적으로 제외한 것**: 관리자 전용 CRUD(M002), AI 자연어 상담·조건 추출·일정 생성·환각 방지 등(M003 전체),
후기(리뷰) 관리(M001-F-007/M002-F-004, 우선순위 낮음), 날씨 API 연동(M005-F-009), PDF 실제 파일 생성(공유 토큰 발급까지만 구현).

## 프로젝트 구조

```
backend/
  config/                Django 설정, 루트 URL
  apps/
    accounts/             소셜 로그인 + 내 정보 + 로그아웃 (기존 + 확장)
    travel/                관광지/숙소/맛집/패키지 카탈로그 + 최종 일정(Itinerary)
      management/commands/seed_travel_data.py   프론트와 동일한 이름/가격의 샘플 데이터 적재
    reservation/           장바구니 + 예약 요청 (신규 앱)
    bookmark/               찜하기
    history/                이용 기록 로그
      management/commands/load_fake_history.py  fake_data.json → History 테이블 적재
  fake_data.json
  manage.py
  requirements.txt
  .env.example
```

## 실행 방법

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example ../.env     # 프로젝트 루트(backend의 상위)에 .env 생성 후 GOOGLE_CLIENT_ID 채우기

python manage.py migrate
python manage.py seed_travel_data     # 프론트와 동일한 패키지/관광지/맛집/숙소 시드
python manage.py load_fake_history    # fake_data.json 적재 (선택)
python manage.py createsuperuser      # /admin/ 에서 데이터 확인용 (선택)

python manage.py runserver
```

- API 문서(Swagger UI): `http://localhost:8000/swagger/`
- OpenAPI 스키마: `http://localhost:8000/api/schema/`
- Django Admin(데이터 확인용, 관리자 "기능"이 아니라 개발 편의용): `http://localhost:8000/admin/`

### Swagger / OpenAPI 문서화 상태

`drf-spectacular`로 **코드에서 자동 생성**됩니다(별도로 손으로 쓴 명세서가 아니라, 모델·시리얼라이저·뷰를
기반으로 매번 최신 상태가 자동 반영되는 방식입니다). 총 27개 엔드포인트가 전부 Swagger UI에 노출되며,
`python manage.py spectacular --validate` 기준 **경고 0건**으로 스키마가 생성됩니다.

- ModelViewSet/ReadOnlyModelViewSet 기반 엔드포인트(카탈로그, 일정)는 시리얼라이저에서 자동으로 요청/응답
  스키마가 추출됩니다.
- 순수 `APIView`로 만든 엔드포인트(로그인/로그아웃/내정보, 장바구니, 예약, 찜, 이용기록)는
  `@extend_schema(request=..., responses=...)`를 각 메서드에 직접 달아 요청/응답 형태를 명시했습니다.
- `Itinerary`의 계산 필드(`total_cost`, `duration_label`, `cost_breakdown`)와 관광지의 `tags`처럼
  일반적으로 타입 추론이 안 되는 필드들도 타입 힌트/`@extend_schema_field`로 정확한 타입이 나오도록 처리했습니다.

## 인증

- 로그인은 프론트에서 구글/카카오 SDK로 받은 토큰을 아래 엔드포인트로 보내면 JWT(`access`/`refresh`)를 발급합니다.
- 이후 모든 인증 필요 API는 `Authorization: Bearer <access>` 헤더를 사용합니다.
- (테스트용) 실제 구글/카카오 없이 확인하려면 Django shell에서 `RefreshToken.for_user(user)`로 토큰을 직접 발급할 수 있습니다.

## API 엔드포인트

### 계정 (`/api/accounts/`)

| Method | URL | 설명 | 인증 |
|---|---|---|---|
| POST | `/api/accounts/google/` | 구글 로그인 (`{token}`) → JWT 발급 | - |
| POST | `/api/accounts/kakao/` | 카카오 로그인 (`{token}`) → JWT 발급 | - |
| POST | `/api/accounts/logout/` | 로그아웃 (`{refresh}` 블랙리스트 처리) | ✓ |
| GET | `/api/accounts/me/` | 내 정보 조회 | ✓ |
| PATCH | `/api/accounts/me/` | 내 정보 수정 (닉네임/연락처/여행 선호) | ✓ |
| POST | `/api/token/refresh/` | 액세스 토큰 재발급 | - |

### 카탈로그 (`/api/travel/`) — 읽기 전용, 로그인 불필요

| Method | URL | 설명 |
|---|---|---|
| GET | `/api/travel/spots/` | 관광지 목록 (`?q=`, `?tag=`) |
| GET | `/api/travel/spots/{id}/` | 관광지 상세 |
| GET | `/api/travel/accommodations/` | 숙소 목록/상세 |
| GET | `/api/travel/restaurants/` | 맛집 목록 (`?category=`) |
| GET | `/api/travel/packages/` | 패키지 목록 (`?style=`, `?category=`, `?duration_days=`, `?max_price=`) |
| GET | `/api/travel/packages/{id}/` | 패키지 상세 (가격/코스/포함항목/숙소포함여부) |

### 최종 일정 (`/api/travel/itineraries/`) — 로그인 필요, 본인 소유만 접근

| Method | URL | 설명 |
|---|---|---|
| GET | `/itineraries/` | 내 일정 목록 |
| POST | `/itineraries/` | 일정 생성 (days/items 중첩 포함 가능) |
| GET | `/itineraries/{id}/` | 일정 상세 (총비용/카테고리별 비용/일자별 항목 포함) |
| PUT/PATCH | `/itineraries/{id}/` | 일정 수정 (부분 수정 시 `days` 생략하면 기존 일정 유지) |
| DELETE | `/itineraries/{id}/` | 일정 삭제 |
| GET | `/itineraries/{id}/route/` | 일자별 순서대로의 좌표 목록 (지도 표시용) |
| POST | `/itineraries/{id}/share/` | 공유 토큰 발급 |
| GET | `/itineraries/shared/{token}/` | 공유 링크로 읽기 전용 조회 (로그인 불필요) |

`days`를 포함해 PATCH하면 **해당 일정의 모든 day/item을 통째로 교체**합니다(단순하고 예측 가능한 저장 방식).
개별 항목만 바꾸고 싶다면 전체 `days` 배열을 다시 보내주세요.

### 장바구니 / 예약 (`/api/`) — 로그인 필요

| Method | URL | 설명 |
|---|---|---|
| GET | `/api/cart/` | 장바구니 조회 (담긴 패키지 + 합계) |
| POST | `/api/cart/` | 장바구니에 패키지 담기 (`{package_id}`) |
| DELETE | `/api/cart/{cart_item_id}/` | 장바구니에서 제거 |
| GET | `/api/reservations/` | 예약 내역 조회 |
| POST | `/api/reservations/` | 예약 요청(시연). `{}`만 보내면 장바구니 전체를 예약으로 전환, `{package_ids:[...]}`로 특정 패키지만 즉시 예약도 가능. 성공 시 결제 없이 바로 `confirmed` 처리되고 장바구니에서는 제거됨 |
| GET | `/api/reservations/{id}/` | 예약 상세 |

### 찜하기 (`/api/bookmarks/`) — 로그인 필요

| Method | URL | 설명 |
|---|---|---|
| GET | `/api/bookmarks/` | 내 찜 목록 |
| POST | `/api/bookmarks/` | 찜하기 (`{package_id}`) |
| DELETE | `/api/bookmarks/{id}/` | 찜 해제 |

### 이용 기록 (`/api/history/`) — 로그인 필요

| Method | URL | 설명 |
|---|---|---|
| GET | `/api/history/` | 내 이용 기록 조회 |
| POST | `/api/history/` | 이용 기록 남기기 (`{action, detail}`, date/time은 생략 시 서버가 현재 시각으로 채움) |

## 프론트엔드 연동 시 참고

- 아직 프론트와 실제로 연결하지 않았습니다(요청하신 대로). CORS는 `http://localhost:5173`을 기본 허용하도록 미리 설정해뒀습니다.
- `seed_travel_data`로 넣은 패키지 3종(오션뷰 힐링 숙소 159,000원 / 렌터카 3일 89,700원 / 제주 승마 체험 2인 70,000원)은
  프론트 `/booking` 페이지의 `PACKAGES` 목업과 이름·가격이 동일합니다. 나중에 연결할 때 프론트의 하드코딩된
  배열을 이 API 응답으로 바꾸기만 하면 되도록 맞춰뒀습니다.
- `/review` 페이지의 "여행 요약" 비용 카테고리(숙소/렌터카/액티비티/식비/기타)는
  `Itinerary` 모델의 `accommodation_cost/transport_cost/activity_cost/food_cost/etc_cost` 및
  `cost_breakdown`/`total_cost` 필드와 1:1로 대응됩니다.
- AI 채팅(`/chat`)이 실제로 붙게 되면, 대화가 끝나는 시점에 `POST /api/travel/itineraries/`로
  추천 결과(일자별 items)를 그대로 저장하고, `/itinerary`·`/review` 페이지는 그 응답을 그대로 렌더링하면 됩니다.

## 스모크 테스트 결과 (2026-07-25 확인)

`migrate` → `seed_travel_data` → `runserver` 후 다음을 모두 실제로 호출해 정상 동작을 확인했습니다:

- `GET /api/travel/packages/` (200)
- `GET /api/accounts/me/` (200), `PATCH` 없이도 조회 가능
- `POST /api/cart/` ×2 → `GET /api/cart/` (담긴 항목·합계 정상)
- `POST /api/reservations/` (장바구니 → 예약 전환, 총액/스냅샷 정상, 장바구니 비워짐)
- `POST /api/travel/itineraries/` (2박 3일, 2일치 items 포함) → `total_cost: 438,700` (프론트 목업과 동일한 값)
- `GET /itineraries/{id}/route/` (일자별 좌표 정상 반환)
- `POST /itineraries/{id}/share/` (토큰 발급 정상)
- `PATCH /itineraries/{id}/` (일부 필드만 수정 시 기존 `days` 보존 확인)
- `POST /api/bookmarks/`, `GET /api/bookmarks/` (정상)
- `GET/POST /api/history/` (정상, 사용자별로 격리됨)
- `POST /api/accounts/logout/` (블랙리스트 처리, 205 응답)
- `/api/schema/` (drf-spectacular 스키마 생성 정상)

## 남은 작업 (다음 단계 제안)

- 프론트엔드 연동: axios/fetch 클라이언트, JWT 저장(refresh 로직 포함), 각 목업 데이터를 API 응답으로 교체
- AI(RAG) 서비스가 준비되면 `/chat` 완료 시점에 일정을 `POST /itineraries/`로 저장하는 연동 지점 추가
- 필요 시 후기(Review) 기능, 날씨 API 프록시 추가 (요구사항상 선택 항목이라 이번 범위에서 제외)
- 운영 배포 시 `DEBUG=False`, `ALLOWED_HOSTS`, 실제 DB(MySQL 등) 전환 필요 (`요구사항 정의서`의 손글씨 메모에 MySQL 사용 의도가 있어 현재 SQLite는 로컬 개발용으로만 사용 권장)
