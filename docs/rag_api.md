# 여행 일정 LLM용 장소 검색 API

`src.rag`는 TourAPI MySQL과 ChromaDB를 한 번에 조회하는 동기식 Python API입니다.
여행 일정 생성 팀은 DB별 연결 코드를 작성하지 않고 이 모듈만 호출하면 됩니다.

## 검색 흐름

1. MySQL에서 RAG 사용 여부, 카테고리, 일정 사용 여부 등의 필수 조건을 검사합니다.
2. 허용된 장소만 ChromaDB에서 의미 기반으로 검색합니다.
3. 주소, 운영시간, 주차, 요금, 이미지 등 최신 상세정보를 MySQL에서 다시 조회합니다.
4. `MATCHED` 상태의 AIHub 매핑만 방문·만족도 근거로 붙입니다.

벡터 메타데이터가 아니라 MySQL을 최종 상세정보의 기준으로 사용합니다.

## 기본 사용법

```python
from src.rag import PlaceSearchFilters, search_places

response = search_places(
    "부모님과 조용히 산책하기 좋은 제주 관광지",
    filters=PlaceSearchFilters(
        target_collections=("attractions",),
        itinerary_roles=("visit",),
        recommendation_scopes=("default",),
        route_eligible=True,
        schedule_eligible=True,
    ),
    top_k=8,
)

for place in response.places:
    print(place.title, place.opening_hours, place.similarity_score)
```

`response.to_dict()`는 API 응답 등에 사용할 수 있는 딕셔너리를 반환합니다.

## LLM 프롬프트용 컨텍스트

```python
from src.rag import PlaceSearchFilters, build_rag_context

context_json = build_rag_context(
    "아이와 비 오는 날 방문할 실내 체험",
    filters=PlaceSearchFilters(
        target_collections=("attractions", "activities"),
        schedule_eligible=True,
    ),
    top_k=6,
)
```

`context_json`에는 장소 ID, 좌표, 운영시간, 휴무일, 주차, 예약, 요금,
검색 점수와 AIHub 근거가 포함됩니다. LLM에는 이 JSON을 참고 자료로 전달하고,
운영시간이나 요금을 추측하지 않도록 프롬프트에서 명시해야 합니다.

## 숙소 검색

숙소는 일반 관광 동선에 섞이지 않도록 `intent_only` 범위로 저장되어 있습니다.

```python
from src.rag import PlaceSearchFilters, search_places

lodgings = search_places(
    "서귀포 수영장이 있는 가족 숙소",
    filters=PlaceSearchFilters(
        target_collections=("lodgings",),
        itinerary_roles=("stay",),
        recommendation_scopes=("intent_only",),
        route_eligible=True,
    ),
    top_k=5,
)
```

## 장소 ID로 상세정보 조회

```python
from src.rag import get_places_by_ids

places = get_places_by_ids([1884191, 2792568])
```

이 함수는 임베딩 API를 호출하지 않고 MySQL만 조회합니다.

## 서비스 객체 재사용

요청마다 객체를 만들지 않고 애플리케이션 시작 시 한 번 생성할 수도 있습니다.

```python
from pathlib import Path
from src.rag import create_place_search_service

service = create_place_search_service(project_root=Path.cwd())
response = service.search_places("제주 동쪽 해안 산책", top_k=5)
```

기본적으로 프로젝트 루트의 `.env`를 읽으며 기존 프로세스 환경변수를 덮어쓰지
않습니다. 필요한 설정은 `MYSQL_*`, `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`,
`CHROMA_*`입니다.
