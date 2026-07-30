# LLM·RAG 평가 하네스

이 프로젝트의 평가 코드는 OpenAI의
[Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
원칙을 현재 제주 여행 RAG에 맞게 적용합니다.

OpenAI가 권장하는 핵심 원칙은 다음과 같습니다.

- 실제 업무에 맞는 목적과 성공 기준을 먼저 정의
- 일반적인 점수보다 골든셋 기반의 과업별 평가 사용
- 검색과 생성처럼 비결정성이 생기는 단계를 각각 평가
- 자동화된 지표를 사람의 판단과 주기적으로 보정
- 일반·경계·적대 사례를 포함하고 변경 때마다 지속 평가
- LLM 심사는 모호한 자유 채점보다 pass/fail·분류·비교 중심으로 구성

OpenAI 공식 가이드의 문서 Q&A 예시는 `context recall >= 0.85`,
`context precision > 0.70`을 출발 기준으로 제시합니다. 이 프로젝트도 같은
기본값을 사용하지만, 실제 서비스 데이터에 맞춰 사람이 검수한 골든셋으로
임계값을 다시 보정해야 합니다.

OpenAI Evals 플랫폼은 2026년 종료 예정이므로 이 코드는 해당 원격 플랫폼에
의존하지 않습니다. 골든셋·러너·채점·결과물을 프로젝트 내부에서 재현할 수
있는 로컬 하네스로 제공합니다.

## 평가 대상

### 1. LLM 조건 추출

- 단일값 필드 정확도
- 선호·제외 목록 F1
- 누락 조건의 재질문 상태
- 날짜·동행자·교통·시간 제한 지시 준수

### 2. RAG 검색

- `context_precision`: 검색 후보 중 골든 관련 장소의 비율
- `context_recall`: 골든 관련 장소 중 실제 검색된 비율
- `retrieval_mrr`: 첫 관련 장소의 역순위

검색 지표를 사용하려면 평가 케이스에 사람이 검수한
`relevant_content_ids`를 넣어야 합니다. 관련 장소를 한두 개만 임의로
지정하면 precision이 왜곡되므로 해당 질의에서 관련하다고 판단되는 장소를
충분히 라벨링해야 합니다.

### 3. 일정 생성과 검증

- 요청 일수와 날짜별 관광지 수
- TourAPI ID 화이트리스트 근거성
- 필수 장소 포함률과 제외조건 준수
- 중복 장소 여부
- 설명·선택 이유 제공률
- 운영시간·거리 검증 통과
- 경로 공급자 검증 적용률

화이트리스트, 운영시간, 필수 장소처럼 코드로 판별 가능한 항목은 LLM에게
채점시키지 않고 결정론적으로 검사합니다.

### 4. 선택적 LLM 심사

`--llm-judge`를 지정했을 때만 다음 항목을 별도 pass/fail로 평가합니다.

- 사용자 지시 준수
- 동행자·선호 조건 적합성
- 동선과 시간 흐름의 자연스러움
- 장소 설명과 선택 이유의 품질

LLM 심사는 위치 편향·장문 선호 같은 편향이 있으므로 사람 라벨과 일치도를
확인하기 전에는 단독 출시 기준으로 사용하지 않습니다.

## 골든셋

초기 골든셋:

```text
evals/rag/golden_cases.jsonl
```

현재 파일은 평가 코드 검증용 소규모 시작 세트입니다. 출시 기준으로
사용하려면 실제 사용자 로그와 전문가 검수 사례를 포함해 최소 50~100개의
다양한 사례로 확장하는 것을 권장합니다. 개인식별정보는 제거해야 합니다.

## 실행

프로젝트 루트에서 실행합니다.

### 빠른 2개 사례

```powershell
conda activate dl_nlp_env
cd /d C:\Users\Playdata\Desktop\SKN28-FINAL-2Team
python -m scripts.evaluation.run_rag_evaluation --max-cases 2 --no-fail
```

이 명령은 실제 조건 추출·일정 생성 OpenAI 호출을 수행할 수 있습니다.
`--no-fail`은 기준 미달이어도 베이스라인 결과를 저장하고 종료코드 0을
반환합니다.

특정 사례만 실행하려면 다음과 같이 지정합니다.

```powershell
python -m scripts.evaluation.run_rag_evaluation `
  --case-id rag_halla_arboretum `
  --no-fail
```

### 전체 골든셋

```powershell
python -m scripts.evaluation.run_rag_evaluation
```

### 선택적 LLM 심사 포함

```powershell
python -m scripts.evaluation.run_rag_evaluation --llm-judge
```

LLM 심사 모델은 `.env`의 `OPENAI_EVAL_JUDGE_MODEL`을 사용합니다. 같은 모델이
자기 결과를 심사하면 편향될 수 있으므로, 공식적인 비교 평가에서는 강한
별도 모델을 사용하고 사람 라벨과 합치도를 확인하는 편이 좋습니다.

### 약 120회 반복

현재 골든셋이 8개이므로 다음 명령은 총 120개 실행 결과를 만듭니다.

```powershell
python -m scripts.evaluation.run_rag_evaluation --repeat 15 --no-fail
```

실제 OpenAI 비용이 발생합니다. 먼저 `--max-cases 1`로 계약과 비용을 확인한
후 반복 실행하는 것을 권장합니다.

## OpenAI 호출 없이 저장 결과 재채점

다음 JSONL 형식으로 기존 결과를 준비합니다.

```json
{"case_id":"rag_halla_arboretum","result":{"status":"completed","conditions":{},"slot_candidates":[],"itinerary":[],"validation":{}}}
```

실행:

```powershell
python -m scripts.evaluation.run_rag_evaluation `
  --offline-results artifacts\saved_results.jsonl `
  --no-fail
```

## 결과

기본 결과 폴더:

```text
artifacts/rag_evaluation/
```

- `rag-eval-*.json`: 케이스별 지표, 실패 태그, 지연시간, 토큰 사용량
- `rag-eval-*.md`: 사람이 확인하기 쉬운 요약표

기본 실행에서는 사용자 원문과 전체 RAG 결과를 결과 파일에 복제하지
않습니다. 디버깅 목적으로 필요할 때만 `--include-results`를 사용합니다.

## CI 출시 기준

결정론적 단위 테스트:

```powershell
python -m pytest tests\rag\test_evaluation.py -q
```

전체 RAG 회귀 테스트:

```powershell
python -m pytest tests\rag -q
```

평가 실패 원인은 `failure_tags`로 집계됩니다. 프롬프트·검색 가중치·검증
정책·모델을 변경했을 때 같은 골든셋을 다시 실행하고, 기존 베이스라인보다
통과율이나 핵심 지표가 낮아지면 배포를 중단하도록 CI에서 사용할 수 있습니다.
