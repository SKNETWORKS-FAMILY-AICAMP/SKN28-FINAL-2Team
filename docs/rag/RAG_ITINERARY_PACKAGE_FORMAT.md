# RAG 일정 양식 및 가상 패키지 변환 명세

## 1. 문서 목적

이 문서는 `src/rag`가 생성한 일정을 가상 여행 패키지 상품 제작에 전달하기
위한 JSON 형식을 정의한다. RAG의 원본 응답과 상품용 JSON은 목적이 다르므로
두 형식을 구분한다.

- **RAG 원본 일정:** 검색·생성·검증 결과를 포함한 내부 계약
- **가상 패키지 일정:** 화면 표시와 상품 카탈로그 적재에 적합한 계약

가상 패키지는 반드시 다음 조건을 만족한 RAG 결과만 사용한다.

```text
status == "completed"
validation.valid == true
```

`validation_failed`, `retrieval_incomplete`, `clarification_required` 결과는
상품으로 확정하지 않는다.

---

## 2. 현재 RAG 일정 구성 정책

기본적으로 하루 일정은 다음 순서로 구성한다.

```text
선택적 아침 식사
→ 오전 관광지
→ 점심 식사
→ 오후 관광지
→ 늦은 오후 관광지
→ 저녁 식사
```

- 관광지는 매일 정확히 3곳을 선정한다.
- 점심과 저녁은 관광지 3곳과 별도인 식사 슬롯이다.
- 아침 식사는 사용자가 요청한 경우에만 추가한다.
- 사용자가 제외한 식사 슬롯은 일정에서 생략할 수 있다.
- 숙소는 현재 관광지로 선정하지 않고 일별 출발·복귀 동선의 기준점으로만
  사용한다.
- 장소는 TourAPI `content_id` 화이트리스트 안에서만 확정한다.
- AIHub 동선이 있으면 권역·순서·체류시간을 참고한다.
- AIHub 동선이 전혀 없으면 TourAPI 단독 폴백을 사용할 수 있다.

### 내부 슬롯 번호

| 종류 | 내부 `sequence` |
|---|---:|
| 오전 관광지 | 1 |
| 오후 관광지 | 2 |
| 늦은 오후 관광지 | 3 |
| 아침 식사 | 101 |
| 점심 식사 | 102 |
| 저녁 식사 | 103 |

`sequence`는 내부 슬롯 식별자이며 화면의 방문 순서를 의미하지 않는다.
상품 일정에서는 반드시 `day`, `start_time` 순으로 정렬한 뒤 별도의
`display_order`를 1부터 부여한다.

---

## 3. RAG 원본 응답

```json
{
  "status": "completed",
  "conditions": {},
  "itinerary": [],
  "validation": {
    "valid": true,
    "issues": [],
    "schedule": []
  },
  "meta": {
    "route_strategy": "aihub_pattern",
    "aihub_used": true,
    "tourapi_rag_used": true,
    "tourism_places_per_day": 3
  }
}
```

### `itinerary` 항목

```json
{
  "day": 1,
  "sequence": 1,
  "content_id": 100001,
  "title": "한라수목원",
  "start_time": "09:00",
  "end_time": "10:30",
  "stay_minutes": 90,
  "distance_from_previous_km": 3.2,
  "description": "제주 자생식물과 아열대식물을 관찰할 수 있는 도심 속 수목원입니다. 산책하며 쉬기 좋은 장소입니다.",
  "reason": "자연 선호와 부모님 동반 조건, 짧은 이동거리를 반영해 선택했습니다.",
  "selection_reason": "자연 선호와 부모님 동반 조건, 짧은 이동거리를 반영해 선택했습니다.",
  "source": "TourAPI",
  "slot_kind": "tourism",
  "meal_type": null
}
```

### 필드 설명

| 필드 | 형식 | 설명 |
|---|---|---|
| `day` | integer | 여행 일차, 1부터 시작 |
| `sequence` | integer | RAG 내부 슬롯 번호 |
| `content_id` | integer | TourAPI 장소 고유 ID |
| `title` | string | 장소 또는 식당 이름 |
| `start_time` | `HH:MM` | 방문 시작 시각 |
| `end_time` | `HH:MM` | 방문 종료 시각 |
| `stay_minutes` | integer | 체류시간(분) |
| `distance_from_previous_km` | number/null | 이전 일정에서의 직선거리 |
| `description` | string | TourAPI 소개를 최대 2문장으로 정리한 설명 |
| `selection_reason` | string | 사용자 조건과 검색 근거를 반영한 선택 이유 |
| `reason` | string | `selection_reason`과 같은 값인 호환 필드 |
| `source` | string | 현재 확정 장소 출처인 `TourAPI` |
| `slot_kind` | string | `tourism` 또는 `meal` |
| `meal_type` | string/null | `breakfast`, `lunch`, `dinner` 또는 null |

---

## 4. 가상 패키지 권장 형식

RAG 원본 응답을 상품 DB에 그대로 저장하지 않고 다음과 같은 상품용 형식으로
변환하는 것을 권장한다.

```json
{
  "schema_version": "1.0",
  "package_id": "VIRTUAL-JEJU-2N3D-001",
  "is_virtual": true,
  "title": "제주 2박 3일 부모님 동반 힐링 여행",
  "summary": "제주의 숲과 해안 풍경을 여유롭게 둘러보는 2박 3일 가상 패키지입니다.",
  "duration": {
    "nights": 2,
    "days": 3
  },
  "target": {
    "party_type": "with_parents",
    "min_people": 2,
    "max_people": 4
  },
  "themes": ["nature", "culture", "relaxed"],
  "transport": "rental_car",
  "accommodation": {},
  "pricing": {},
  "includes": [],
  "excludes": [],
  "days": [],
  "source": {},
  "disclaimer": "실제 판매 상품이 아닌 시연용 가상 패키지입니다."
}
```

### 패키지 필수 필드

| 필드 | 설명 |
|---|---|
| `schema_version` | 상품 양식 버전 |
| `package_id` | 가상 상품 고유 ID |
| `is_virtual` | 반드시 true |
| `title` | 상품명 |
| `summary` | 상품 소개 |
| `duration` | 숙박 수와 여행 일수 |
| `target` | 권장 동행 유형과 인원 |
| `themes` | 자연·문화·힐링 등 상품 테마 |
| `transport` | 렌터카·대중교통 등 이동수단 |
| `accommodation` | 숙소 상품 정보. RAG 관광 일정과 별도 관리 |
| `pricing` | 1인 기준 가격과 항목별 금액 |
| `includes` | 상품 포함 사항 |
| `excludes` | 상품 불포함 사항 |
| `days` | 날짜별 일정 |
| `source` | RAG 생성·검증 출처 |
| `disclaimer` | 가상 상품 안내 |

### 날짜별 상품 일정

```json
{
  "day": 1,
  "date": null,
  "title": "제주시 숲과 문화 코스",
  "route_summary": "제주공항 → 한라수목원 → 점심 → 문화 관광지 → 해안 관광지",
  "items": [
    {
      "display_order": 1,
      "source_sequence": 1,
      "tourapi_content_id": 100001,
      "item_type": "tourism",
      "meal_type": null,
      "title": "한라수목원",
      "start_time": "09:00",
      "end_time": "10:30",
      "stay_minutes": 90,
      "description": "제주 자생식물과 아열대식물을 관찰할 수 있는 도심 속 수목원입니다.",
      "selection_reason": "자연 선호와 부모님 동반 조건, 짧은 이동거리를 반영했습니다.",
      "estimated_price": {
        "amount": 0,
        "currency": "KRW",
        "status": "virtual_estimate"
      }
    }
  ]
}
```

### 패키지 가격 형식

```json
{
  "currency": "KRW",
  "price_basis": "per_person",
  "total_amount": 438700,
  "status": "virtual_estimate",
  "breakdown": {
    "accommodation": 159000,
    "transportation": 89700,
    "activities": 70000,
    "meals": 90000,
    "other": 30000
  }
}
```

가상 가격에는 반드시 `status: "virtual_estimate"`를 표시한다. TourAPI의
요금 문자열이 비어 있거나 최신 여부를 확인할 수 없으면 실제 판매가로
사용하지 않는다.

---

## 5. RAG 일정에서 패키지 일정으로 변환하는 규칙

1. `status=completed`, `validation.valid=true`인지 확인한다.
2. `itinerary`를 `day`, `start_time` 오름차순으로 정렬한다.
3. 일자별로 묶고 `display_order`를 1부터 새로 부여한다.
4. `content_id`를 `tourapi_content_id`로 옮긴다.
5. `sequence`를 `source_sequence`에 보존한다.
6. `slot_kind`를 `item_type`으로 옮긴다.
7. `description`과 `selection_reason`을 상품 화면에 표시한다.
8. 가격은 별도 가상 상품 DB에서 결합한다.
9. 숙소·렌터카·액티비티 상품은 관광 일정과 별도 카탈로그에서 결합한다.
10. RAG 검증 경고가 하나라도 있으면 상품을 `draft` 상태로 유지한다.

---

## 6. 상품 제작 시 주의사항

- RAG는 관광지와 식당의 방문 일정을 생성하며 예약을 보장하지 않는다.
- 숙소는 현재 RAG가 자동 선정하는 관광 슬롯이 아니다.
- `distance_from_previous_km`는 현재 직선거리이므로 실제 도로 이동거리는
  지도 API 결과로 교체해야 한다.
- 운영시간과 요금은 상품 확정 전에 최신 데이터로 다시 확인해야 한다.
- 가상 가격, 평점, 예약 가능 여부를 실제 정보처럼 표시하지 않는다.
- TourAPI `content_id`가 없는 임의 장소를 RAG 확정 장소로 추가하지 않는다.

전체 예시는
[`virtual_package_2n3d.example.json`](examples/virtual_package_2n3d.example.json)
에서 확인할 수 있다. 형식 자동 검증에는
[`virtual_package.schema.json`](examples/virtual_package.schema.json)을
사용한다.
