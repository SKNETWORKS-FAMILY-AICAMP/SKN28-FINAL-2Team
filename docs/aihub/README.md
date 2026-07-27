# AIHub 데이터 파이프라인

AIHub 국내 여행 데이터를 제주 지역 기준으로 전처리하고 MySQL에 적재한 뒤,
AIHub 방문 장소를 TourAPI 장소와 비교·매핑하는 파이프라인입니다.
AIHub 임베딩 또는 AIHub 전용 벡터 DB 생성 단계는 포함하지 않습니다.

TourAPI와 AIHub는 별도 데이터베이스를 만들지 않고 `.env`의
`MYSQL_DATABASE` 하나를 함께 사용합니다. TourAPI 테이블과 `aihub_` 접두사의
AIHub 테이블은 이름이 겹치지 않으며, `aihub_places.tourapi_content_id`가 같은
데이터베이스의 `places.content_id`를 참조합니다.

## 처리 범위

1. AIHub 원본 여행 로그에서 제주 데이터와 필요한 코드 테이블을 추출합니다.
2. 전처리 CSV의 컬럼과 행 수를 검증하고 AIHub MySQL 테이블에 적재합니다.
3. AIHub 방문 기록을 장소 단위로 묶어 TourAPI RAG 장소와 매핑합니다.
4. 매핑 결과에서 프랜차이즈와 비관광 장소를 분리합니다.
5. 추천 후보와 TourAPI 원본의 포함·누락 상태를 비교해 CSV로 내보냅니다.

## 주요 파일

| 역할 | 경로 |
| --- | --- |
| 로컬 AIHub 원본 | `data/raw/` |
| MySQL 적재용 CSV | `data/processed/aihub/data/` |
| 코드 테이블 | `data/processed/aihub/code/` |
| 전처리 검증 보고서 | `data/processed/aihub/reports/` |
| 매핑·비교 결과 | `data/processed/aihub/exports/` |
| 전처리 서비스 | `src/aihub/preprocessing.py` |
| 장소 식별·그룹화 | `src/aihub/place_identity.py` |
| TourAPI 장소 매칭 | `src/aihub/place_mapping.py` |
| 매핑·DB 적재 서비스 | `src/aihub/mapping_pipeline.py` |
| 필터 규칙 | `src/aihub/configs/` |
| MySQL 스키마·검증 SQL | `src/aihub/sql/` |
| 실행 진입점 | `scripts/preprocessing/`, `scripts/storage/` |

`scripts/`는 명령행 인자와 결과 출력만 담당하고, 재사용 가능한 전처리·매핑
로직은 `src/aihub/`에 둡니다.

AIHub 원본은 용량과 배포 조건 때문에 Git에서 제외합니다. 전처리 기본 입력은
`data/raw/`, 기본 출력은 `data/processed/aihub/`이며 필요하면
`--dataset-root`, `--output-root`로 변경할 수 있습니다.

현재 포함된 전처리 데이터의 MySQL dry-run 기준은 13개 테이블,
총 141,322행입니다. 주요 내보내기 결과는 다음과 같습니다.

| 산출물 | 행 수 |
| --- | ---: |
| `aihub_tourapi_place_mappings.csv` | 7,642 |
| `aihub_tour_recommendation_places.csv` | 7,076 |
| `aihub_tour_recommendation_excluded.csv` | 566 |
| `aihub_tourapi_raw_comparison.csv` | 2,124 |

## 준비

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

MySQL 적재와 매핑에는 공용 `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`,
`MYSQL_PASSWORD`, `MYSQL_DATABASE` 설정이 필요합니다.
장소 매핑은 TourAPI 전처리 결과
`data/processed/jeju_place_rag_documents.json`을 기본 기준으로 사용합니다.

## 실행 순서

```powershell
# 1. AIHub 원본 전처리
python -m scripts.preprocessing.preprocess_aihub_data

# 2. 공용 DB에 TourAPI 스키마와 데이터를 먼저 준비
python -m scripts.storage.manage_tourapi_storage mysql-load

# 3. AIHub 파일 구성과 행 수 검증
python -m scripts.storage.load_aihub_to_mysql --dry-run

# 4. 같은 MYSQL_DATABASE에 AIHub 적재
python -m scripts.storage.load_aihub_to_mysql --replace

# 5. AIHub 장소 그룹화 및 TourAPI 매핑
python -m scripts.preprocessing.map_aihub_places

# 6. 매핑 결과 내보내기
python -m scripts.preprocessing.export_aihub_place_mappings

# 7. 추천 대상과 제외 대상 분리
python -m scripts.preprocessing.filter_aihub_recommendation_places

# 8. 추천 대상과 TourAPI 원본 비교
python -m scripts.preprocessing.compare_aihub_to_tourapi_raw
```

기존 `aihub_` 테이블의 데이터만 지우고 다시 적재하려면
`load_aihub_to_mysql --replace`를 사용합니다. 이 옵션은 다른 테이블을
삭제하지 않습니다.

## 검증

```powershell
python -B -m unittest discover -s tests/aihub -p "test_*.py"
python -m scripts.storage.load_aihub_to_mysql --dry-run
```

구조 이전 후 AIHub 테스트 35개와 MySQL dry-run이 통과했습니다.
실제 MySQL 적재와 매핑은 실행 중인 MySQL과 유효한 환경설정이 있어야
최종 확인할 수 있습니다.

## 관련 문서

- [TourAPI 데이터 파이프라인](../tourapi/README.md)
- [TourAPI 데이터 구조](../tourapi/data_schema.md)
