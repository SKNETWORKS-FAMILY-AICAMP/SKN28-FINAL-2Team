# 일정 기반 패키지 추천 서비스

## 목적

일정 생성 RAG의 결과를 입력받아 `tour_recommender` DB에 적재된 패키지 중 일정과 가장 비슷한 상품 3개를 추천한다. 음식점과 숙소는 추천 결과에 포함하지만, 관광지 일치율 계산에서는 제외한다.

## 추천 우선순위

1. 일정과 패키지의 관광지 `content_id` 정확 일치 개수
2. 같은 날짜에 배치되었는지와 관광지 방문 순서
3. 동반자 유형, 선호 테마, 여행 속도와 `match_profile`의 적합도
4. 정확히 일치하지 않는 일정 관광지와 패키지 관광지의 거리

점수는 정확 일치 70점, 날짜·순서 15점, 사용자 조건 10점, 인접 관광지 5점으로 구성한다. 최종 정렬에서는 점수보다 정확 일치 개수를 먼저 비교하므로, 다른 조건만 좋은 패키지가 관광지 일치 개수가 더 많은 패키지를 추월할 수 없다.

## LLM의 역할

LLM은 DB 검색과 점수 계산을 하지 않는다. 코드가 만든 상위 후보의 근거만 받아 동률 후보의 순서를 보조하고 사용자에게 보여줄 한국어 추천 이유를 만든다. 존재하지 않는 패키지 ID를 반환하거나 호출이 실패하면 규칙 기반 결과로 자동 대체된다.

## 입력

현재 RAG 응답의 `condition` + `itinerary.days[].stops[]` 형식과 기존 `conditions` + 평면 `itinerary[]` 형식을 모두 지원한다. `visit`, `activity`, `tourism`, `spot`, `attraction`만 관광지로 처리한다.

## 실행

`.env`에 MySQL 설정을 입력한 뒤 다음 명령을 실행한다.
DB 이름은 이 저장소의 `MYSQL_DATABASE` 또는 통합 백엔드에서 사용하는
`TRAVEL_DB_NAME` 중 하나로 지정할 수 있다.
로컬 관리자 설정 파일을 사용할 때는 `--env-file ../.mysql-local-admin.env`를
지정하면 `MYSQL_ADMIN_*` 변수도 자동으로 인식한다.

실제 일정 JSON이 아직 없다면 DB에 저장된 당일 패키지 하나로 읽기 전용
연결 테스트를 실행할 수 있다.

```powershell
python scripts/recommend_packages.py --smoke-test --smoke-duration 1 --env-file ../.mysql-local-admin.env
```

`--smoke-duration`은 1부터 5까지 지정할 수 있다. 이 검사는 저장된 패키지의
관광지를 테스트 일정으로 사용하므로 해당 패키지가 정확 일치 1위로 나오면
DB 조회, 점수 계산, 결과 직렬화가 정상이라는 의미다.

```powershell
python scripts/recommend_packages.py --input itinerary.json --top-k 3
```

LLM의 동률 판단과 추천 문구를 사용하려면 `OPENAI_API_KEY`와 `OPENAI_PACKAGE_RECOMMENDATION_MODEL`을 설정하고 `--use-llm`을 추가한다.

```powershell
python scripts/recommend_packages.py --input itinerary.json --top-k 3 --use-llm
```

## 백엔드 연결

백엔드에서는 `MySQLPackageRepository`와 `PackageRecommendationService`를 한 번 생성한 뒤 일정 생성 결과 전체를 `recommend(payload, top_k=3)`에 전달하면 된다. 반환값에는 패키지 기본 정보, 가격, 일자별 관광지·음식점, 숙소, 일치 관광지 ID, 세부 점수와 추천 이유가 포함된다.
