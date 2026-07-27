# AIHub Route + TourAPI Place RAG

> **Ownership boundary:** This package is standalone Python RAG code. It must
> not be connected to or imported from `backend/` until the user explicitly
> authorizes backend integration. See `BOUNDARY.md`.

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
   - 하루 슬롯은 relaxed 3개, balanced 4개, packed 5개를 상한으로 하며
     AIHub 방문 순서를 유지한 채 균등하게 압축합니다.
4. `validation.py`
   - 슬롯별 TourAPI ID 화이트리스트, 중복, 필수·제외 장소, 운영시간,
     일자별 이동거리와 도착·출발 제한시간을 검증합니다.
5. `orchestrator.py`
   - 전체 단계를 연결합니다.
   - LLM 초안이 검증에 실패하면 오류 목록으로 한 번 자동 수정합니다.
   - 재실패 또는 LLM 장애 시 슬롯별 최고 점수 후보를 선택하는 결정론적
     폴백으로 전환합니다.

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
    }
)
```

프론트엔드는 최소한 `duration_days`, `party_type`, `local_transport`,
`preferred_visit_types`를 전달해야 합니다. 결과 일정은 매일 정확히 3개 장소로
구성되며 `itinerary`의 `start_time`, `end_time`으로 시간표를 표시할 수 있습니다.
추가 대화로 선택값을 변경할 때는 `selected_options`와 `message`를 함께 전달합니다.

조건이 부족하면 다음 상태가 반환됩니다.

```json
{
  "status": "clarification_required",
  "clarification_questions": [
    "제주에서는 어떤 교통수단을 이용하시나요?"
  ]
}
```

## 환경변수

- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`,
  `MYSQL_DATABASE`
- TourAPI와 AIHub 정형 데이터는 동일한 `MYSQL_DATABASE`를 사용합니다.
- `CHROMA_MODE`, `CHROMA_PERSIST_DIRECTORY`, `CHROMA_COLLECTION`
