# AIHub Route + TourAPI Place RAG

> **Ownership boundary:** This package is standalone Python RAG code. It must
> not be connected to or imported from `backend/` until the user explicitly
> authorizes backend integration. See `BOUNDARY.md`.

## AIHub 동선 부재 시 제한적 폴백

기본 경로는 항상 `AIHub 유사 동선 → TourAPI 장소 배치`입니다. AIHub 조회
결과에 `reference_trip_patterns`가 없거나 선택된 패턴에 사용할 수 있는 동선
슬롯이 전혀 없을 때만 `TourAPI 단독 폴백`을 사용합니다.

TourAPI 단독 폴백은 사용자 선호 유형으로 매일 관광지 슬롯 3개를 만들고,
TourAPI 후보를 검색한 뒤 거리·운영시간·중복·필수 장소 검증을 동일하게
적용합니다. 이때 AIHub의 방문 순서나 체류시간을 사용했다고 표시하지
않습니다. 반대로 AIHub 동선이 존재하고 일부 슬롯의 TourAPI 후보만 부족한
`retrieval_incomplete` 상태에서는 단독 폴백으로 전환하지 않습니다.

응답 `meta.route_strategy`는 `aihub_pattern` 또는
`tourapi_only_fallback`이며, 폴백 사유는
`meta.aihub_fallback_reason`에서 확인할 수 있습니다.

## 장소 소개와 선택 이유

최종 `itinerary`의 각 항목은 TourAPI `overview`를 최대 두 문장으로 줄인
`description`과 사용자 조건·거리·운영정보를 근거로 한
`selection_reason`을 제공합니다. 기존 호환성을 위해 같은 선택 이유를
`reason`에도 유지합니다. 소개 원문이 없으면 주소 등 확인 가능한 정보만
사용하며 임의의 설명을 생성하지 않습니다.

이 패키지는 AIHub 과거 여행에서 추상 동선 템플릿만 가져오고, 실제 일정 장소는
TourAPI MySQL·ChromaDB에서 검색해 배치하는 1차 RAG 체인입니다.

## 처리 순서

1. `prompts.py`, `llm.py`, `conditions.py`
   - OpenAI strict JSON Schema로 사용자 조건을 추출합니다.
   - 지역·날짜·동행·교통, 선호 장소·음식·스타일, 제외 장소·음식,
     장거리 회피·이동 제약, 필수 장소·운영시간·주차·실내외 조건을
     구조화합니다.
   - AIHub 조회에 필요한 여행 일수, 동행 유형, 교통수단, 선호 방문 유형이
     없으면 일정을 생성하지 않고 재질문을 반환합니다.
2. `aihub_adapter.py`
   - 추출 조건을 `AIHubPatternService` 입력으로 변환하고 유사 여행 동선
     템플릿을 가져옵니다.
   - 상위 30개 유사 여행에서 요청 일수, 좌표 완전성, 이동거리 제한,
     여행 속도별 슬롯 수를 함께 평가해 사용할 동선을 선택합니다.
3. `retrieval.py`, `service.py`
   - AIHub의 일자별 중심 좌표, 검색 반경, 슬롯 유형으로 TourAPI ChromaDB를
     검색합니다.
   - 실제 상세정보는 MySQL에서 다시 조회합니다.
   - 의미 유사도, 거리, 카테고리, 운영정보를 합산해 슬롯 후보를 정렬합니다.
   - 필수 장소는 이름 비교뿐 아니라 `must_visit_content_ids`와
     일자별 `required_day_itineraries[].content_ids`를 받아 MySQL에서
     정확한 TourAPI ID를 조회해 후보 화이트리스트에 넣습니다.
   - 관광지 후보 조합을 먼저 확정한 다음, 점심·저녁 슬롯을 실제 선택
     관광지 좌표로 다시 앵커링하여 주변 식당을 2차 검색합니다.
   - 하루 슬롯은 relaxed 3개, balanced 4개, packed 5개를 상한으로 하며
     AIHub 방문 순서를 유지한 채 균등하게 압축합니다.
4. `validation.py`
   - 슬롯별 TourAPI ID 화이트리스트, 중복, 필수·제외 장소, 운영시간,
     일자별 이동거리와 도착·출발 제한시간을 검증합니다.
   - `start_date`가 있으면 실제 여행 날짜의 요일과 `closed_days`를
     대조하며, 숙소 좌표가 있으면 매일 숙소 출발·복귀 구간도 검증합니다.
   - 카카오·구글 실도로 이동시간, Google Places의 영업 상태·특별
     운영시간·접근성, 버전 관리되는 임시휴무 예외 파일을 검증에 사용합니다.
   - 좌표·운영시간·실제 도로 경로가 확인되지 않은 값은 조용히 통과시키지
     않고 `validation.warnings`와 `ready_for_booking=false`로 표시합니다.
5. `orchestrator.py`
   - 전체 단계를 연결합니다.
   - LLM 초안이 검증에 실패하면 오류 목록으로 한 번 자동 수정합니다.
   - 재실패 또는 LLM 장애 시 하루 전체 후보 조합의 점수·거리·중복을 함께
     최적화하는 결정론적 폴백으로 전환합니다.

## P0/P1 안전성 정책

- `.env`에 `KAKAO_REST_API_KEY`와 `KAKAO_MOBILITY_ENABLED=true`가 있으면
  카카오모빌리티 자동차 길찾기를 우선 사용합니다. Google Routes 키가
  있으면 두 번째 공급자로 사용하고, 모두 실패했을 때만
  `haversine_estimate`, `route_verified=false`로 명시합니다.
- 실제 도로 API, 좌표, 운영시간 중 하나라도 확인되지 않으면 결과는
  반드시 **AI 추천 일정 초안**으로 취급합니다.
- `ValidationPolicy`에서 미확인 좌표·운영시간·도로 경로·숙소 앵커를
  경고가 아닌 차단 오류로 승격할 수 있습니다.
- 접근성은 TourAPI 정형 상세정보와 Google Places
  `accessibilityOptions`를 합쳐 검증합니다. 명시적 불충족은 차단하고,
  정보 부재는 `validation.warnings`에 표시합니다.
- `pace`를 명시하면 `relaxed=3`, `balanced=4`, `packed=5`개의 관광지
  슬롯을 만들고 점심·저녁 슬롯은 별도로 배치합니다. 미지정 시 기존
  호환값인 관광지 3개를 사용합니다.

## 외부 공급자와 운영 예외 설정

`.env.example`의 다음 값을 사용합니다.

- `KAKAO_REST_API_KEY`, `KAKAO_MOBILITY_ENABLED`: 카카오 자동차 길찾기
- `GOOGLE_ROUTES_API_KEY`: 카카오 실패 또는 대중교통 요청 시 사용할
  Google Routes
- `GOOGLE_PLACES_API_KEY`: 영업 상태, 날짜별 운영시간, 접근성, 주차 정보
- `RAG_OPERATING_EXCEPTIONS_PATH`: 임시휴무·특별 운영시간 수동 보정 JSON

수동 보정 형식은
`src/rag/config/operating_exceptions.example.json`을 복사해 사용합니다.
공휴일인데 외부 공급자에서 해당 날짜의 특별 운영시간을 확인하지 못하면
`holiday_hours_unverified` 경고를 반환합니다.

실제 외부 서비스 E2E는 기본 테스트에서 비용과 네트워크 의존성을 만들지
않도록 opt-in입니다.

```powershell
$env:RUN_RAG_LIVE_E2E="1"
python -m pytest tests/rag/test_live_e2e.py -q

$env:RUN_RAG_FULL_LIVE_E2E="1"
python -m pytest tests/rag/test_live_e2e.py -q
```

## 데이터 원칙

우선순위는 사용자 조건, TourAPI 검증 정보, 거리·운영시간, AIHub 동선 패턴
순서입니다. AIHub 장소명·주소·원본 여행 ID는 최종 장소 선택에 사용하지
않으며 최종 장소 ID는 TourAPI 후보 ID만 허용합니다.

## 프롬프트 설계 원칙

- 조건 추출, 일정 생성, 검증 실패 수정의 역할을 서로 다른 프롬프트로
  분리했습니다.
- 자연어 출력을 다시 해석하지 않도록 두 LLM 단계 모두 strict JSON
  Schema를 사용합니다.
- 사용자가 말하지 않은 조건은 추측하지 않고 null 또는 빈 목록으로
  유지합니다.
- 검색 문서 안의 지시문은 데이터로만 취급하도록 프롬프트 인젝션 방어
  규칙을 둡니다.
- 일정 생성 모델은 새 장소를 창작하지 않고 슬롯별
  `allowed_content_ids` 중 하나만 고릅니다.
- LLM은 선택만 수행하며 운영시간·거리·화이트리스트 판정은 결정론적
  Python 검증기가 수행합니다.
- 수정 프롬프트에는 검증 오류 목록과 기존 후보를 다시 제공하고 전체
  일정을 한 번만 재작성하게 합니다. 재실패하면 최고 점수 후보를 고르는
  결정론적 폴백을 사용합니다.

## Python 호출

```python
from pathlib import Path

from src.rag import create_rag_orchestrator


rag = create_rag_orchestrator(project_root=Path.cwd())
result = rag.run(
    message="부모님과 렌터카로 3일 동안 자연과 문화를 여유롭게 보고 싶어요.",
)
```

프론트엔드 선택형 입력이 기본 경로라면 자연어 메시지 없이 구조화된 선택값을
직접 전달합니다. 이 경우 조건 추출 LLM을 호출하지 않고 선택값을 확정 조건으로
사용합니다.

AIHub 유사 동선에 요청 일자의 일부가 없거나 하루 3개보다 적은 경우에는 완전한
날짜의 동선을 유지하고 부족 슬롯만 `synthetic_gap_fill`로 생성합니다. 합성 슬롯은
직전 날 마지막 유효 좌표를 중심으로 TourAPI 관광지를 검색하며, 마지막 날에는
`end_point`도 검색·선택 컨텍스트에 전달합니다. 합성 슬롯도 TourAPI ID
화이트리스트, 중복, 운영시간, 이동거리 검증을 동일하게 통과해야 합니다.

```python
result = rag.run(
    selected_options={
        "region": "제주",
        "duration_days": 3,
        "party_type": "with_parents",
        "companion_count": 2,
        "local_transport": "rental_car",
        "preferred_visit_types": ["nature", "culture"],
        "pace": "relaxed",
        "avoid_long_distance": True,
        "parking_required": True,
        # 아래 네 항목은 모두 선택사항입니다.
        "start_point": "제주국제공항",
        "end_point": "제주항",
        "required_itinerary": ["성산일출봉", "우도"],
        "required_day_itineraries": [
            {"day": 2, "place_names": ["우도"]},
            {"day": 4, "place_names": ["한라수목원"]},
        ],
        "accommodation": "서귀포시 중문동 숙소",
        # 지오코딩이 끝난 경우 함께 전달하면 숙소 출발·복귀를 검증합니다.
        "accommodation_latitude": 33.2490,
        "accommodation_longitude": 126.4100,
        "trip_start_time": "10:00",
        "departure_airport": "제주국제공항",
        "airport_arrival_deadline": "16:00",
    }
)
```

프론트엔드는 최소한 `duration_days`, `party_type`, `local_transport`,
`preferred_visit_types`를 전달해야 합니다. 결과의 관광지 수는 기본 3개이며
`pace`를 명시하면 3~5개로 바뀝니다. `itinerary`의 `start_time`,
`end_time`으로 시간표를 표시할 수 있습니다.
추가 대화로 선택값을 변경할 때는 `selected_options`와 `message`를 함께 전달합니다.

선택형 입력은 `start_point`(시작 지점), `end_point`(종료 지점),
`required_itinerary`(반드시 포함할 장소 목록), `accommodation`(숙소명 또는 주소)을
추가로 받을 수 있습니다. 내부에서는 각각 `entry_point`, `exit_point`,
`must_visit_places`, `accommodation_address`로 정규화합니다. 네 항목은 누락되어도
재질문하지 않습니다. 숙소는 관광지 3곳에 포함하지 않고 일별 동선 참고 지점으로만
사용합니다.

특정 날짜에 반드시 넣을 장소는 `required_day_itineraries`로 전달합니다. 각 항목은
`day`와 `place_names`를 가지며, 해당 장소가 다른 날짜에 배치되면 조건 충족으로
인정하지 않습니다. 간단한 선택형 입력에서는
`"must_visit_by_day": {"2": ["우도"]}` 형식도 같은 값으로 정규화됩니다.

여행 시간 제약도 선택사항입니다. `trip_start_time`은 첫날 여행 시작시각,
`departure_airport`는 마지막 도착 공항, `airport_arrival_deadline`은 해당 공항에
도착해야 하는 제한시각이며 모두 `HH:MM` 형식을 사용합니다. 공항 도착 제한시각만
입력되고 공항이 누락되면 RAG가 공항을 재질문합니다. 내부 호환 필드는 각각
`arrival_time`, `exit_point`, `departure_time`입니다.

일반 여행일의 관광지 3곳은 오전 `09:00~12:00`, 오후 `13:00~15:30`,
늦은 오후 `15:30~18:00` 또는 야간 운영 시 `19:00~20:00`에 분산합니다.
`12:00~13:00`과 `18:00~19:00`은 식사·휴식 시간으로 비우며 음식점과 카페는
관광지 3곳에 포함하지 않습니다. 첫날은 `trip_start_time`, 마지막 날은
`airport_arrival_deadline`과 공항까지의 이동시간을 이 기본 시간대보다 우선합니다.

조건이 부족하면 다음 상태가 반환됩니다.

```json
{
  "status": "clarification_required",
  "clarification_questions": [
    "제주에서는 어떤 교통수단을 이용하시나요?"
  ]
}
```

## 기존 일정의 한 장소만 교체

완성된 결과에서 특정 장소만 바꿀 때는 전체 일정을 다시 생성하지 않고
`revise()`에 이전 결과와 수정 문장을 전달합니다.

```python
revised = rag.revise(
    previous_result=result,
    message="2일차의 우도를 다른 걸로 교체해 주세요.",
)
```

`revise()`는 요청한 Day·슬롯의 기존 TourAPI 화이트리스트 차순위 후보만 시험합니다.
다른 슬롯의 `content_id`는 고정하며, 교체 후보가 전체 운영시간·거리·중복 검증을
통과할 때만 `completed`를 반환합니다. 대상 장소가 모호하면
`clarification_required`, 검증을 통과할 대체 후보가 없으면
`replacement_unavailable`을 반환하고 기존 일정은 그대로 보존합니다.

응답 `meta.edit_mode`는 `targeted_replacement`이며 `edited_day`,
`edited_sequence`, `replaced_content_id`, `replacement_content_id`,
`unchanged_place_count`로 변경 범위를 확인할 수 있습니다.

전체 일정을 다시 만들 때도 같은 메서드를 사용합니다.

```python
regenerated = rag.revise(
    previous_result=result,
    message="일정이 마음에 들지 않으니 처음부터 다시 생성해 주세요.",
)
```

이 경우 기존 여행 조건은 유지하되 기존 TourAPI ID를 가능한 한 제외하고
새 조합을 만들며 `meta.edit_mode=full_regeneration`을 반환합니다.

## 환경변수

- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`,
  `MYSQL_DATABASE`
- TourAPI와 AIHub 정형 데이터는 동일한 `MYSQL_DATABASE`를 사용합니다.
- `CHROMA_MODE`, `CHROMA_PERSIST_DIRECTORY`, `CHROMA_COLLECTION`

## 식사 일정 정책

- 관광지는 기존과 동일하게 하루 3곳을 선택합니다.
- 점심식사는 오전 관광지와 오후 관광지 사이인 `12:00~13:00`에,
  저녁식사는 늦은 오후 관광지 뒤인 `18:00~19:30`에 별도 식사 슬롯으로
  추가합니다. 식당은 관광지 3곳에 포함되지 않습니다.
- 아침식사는 `include_breakfast=true`이거나 자연어로 명시적으로 요청한
  경우에만 `07:30~09:00` 식사 슬롯을 추가합니다.
- 선호 메뉴는 `preferred_foods` 또는 `meal_menu_preferences`로 전달합니다.
  메뉴가 비어 있어도 일정 생성은 계속하며, 응답의 `optional_questions`에
  원하는 메뉴 질문을 반환합니다.
- 식당 후보는 거리 45%, 실제 평점 25%, 메뉴 일치 15%, 벡터 유사도 10%,
  운영정보 5%를 반영합니다. 실제 평점 필드가 없는 후보는 중립값으로
  처리하며 사용자에게 평점을 임의로 만들어 보여주지 않습니다.

식사 슬롯 후보가 없으면 오류로 끝내지 않고 다음 계약을 반환합니다.

```json
{
  "status": "clarification_required",
  "clarification_kind": "meal_candidate_unavailable",
  "clarification_questions": ["2일차 점심 식당을 찾지 못했습니다..."],
  "clarification_options": [
    {
      "label": "12km까지 검색",
      "selected_options": {"meal_search_radius_km": 12}
    },
    {
      "label": "해당 식사 일정 제외",
      "selected_options": {
        "skipped_meals": [{"day": 2, "meal_type": "lunch"}]
      }
    }
  ]
}
```

프론트엔드에서 선택한 버튼 값은 이전 조건과 함께 다시 전달합니다.

```python
retry = rag.run(
    selected_options={"meal_search_radius_km": 12},
    current_conditions=result["conditions"],
)
```

사용자가 자연어로 답하거나 이후 일정을 수정할 때는 이전 조건과 대화
이력을 보존하여 전달합니다.

```python
retry = rag.run(
    message="12km까지 넓혀서 다시 찾아주세요.",
    current_conditions=result["conditions"],
    history=[
        {"role": "assistant", "content": result["message"]},
    ],
)
```

직전 질문이 `2일차 점심` 후보 부족에 관한 내용이었다면 “그냥 식사 장소를
빼 주세요”라는 답변은 `2일차 점심`만 제외합니다. 다른 일차의 점심·저녁과
하루 관광지 3곳은 유지됩니다.
