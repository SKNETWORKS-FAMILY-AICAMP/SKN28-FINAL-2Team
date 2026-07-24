# TourAPI 데이터 파이프라인

한국관광공사 TourAPI `KorService2`에서 제주 장소를 수집하고, 추천용 데이터로
전처리한 뒤 MySQL과 ChromaDB에 적재하는 파이프라인입니다.

## 처리 범위

1. LCLS 신분류 코드와 제주 관광·숙박·음식·레저·쇼핑 장소를 수집합니다.
2. 수집 상태를 CSV에 기록해 중단된 API 호출을 이어서 실행합니다.
3. 장소 분류, 제외 정책, 중복 병합을 적용해 RAG 문서 JSON을 생성합니다.
4. 원본과 전처리 결과를 TourAPI MySQL 스키마에 적재합니다.
5. RAG 문서를 OpenAI로 임베딩해 ChromaDB `jeju_places` 컬렉션에 저장합니다.

## 주요 파일

| 역할 | 경로 |
| --- | --- |
| TourAPI 원본 | `data/raw/korea_tour_openapi_jeju_places.csv` |
| LCLS 코드 | `data/raw/korea_tour_openapi_lcls_codes.csv` |
| RAG 문서 | `data/processed/jeju_place_rag_documents.json` |
| 벡터 저장 위치 | `data/vectorstore/` |
| 벡터 manifest | `data/vectorstore/chromadb_manifest.json` |
| 분류·제외 규칙 | `src/tourapi/configs/place_rules.json` |
| MySQL 스키마 | `src/storage/sql/mysql_schema.sql` |
| 수집 로직 | `src/tourapi/crawler/` |
| 전처리 로직 | `src/tourapi/preprocessing/` |
| 장소 분류 로직 | `src/tourapi/preprocessing/classification.py` |
| 임베딩·저장 로직 | `src/embeddings/`, `src/storage/` |

현재 저장된 기준 데이터는 원본 2,124개 장소와 `places-v4` RAG 문서
1,866개입니다. 실제 기준은 항상 RAG JSON과 manifest의
`preprocessing_version`, `document_count`, `sha256`으로 확인합니다.

## 준비

저장소 루트에서 의존성을 설치하고 환경 파일을 준비합니다.

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 필요한 값을 설정합니다.

- 수집: `KOREA_TOUR_API_KEY`
- MySQL: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`,
  `MYSQL_DATABASE`
- 임베딩: `OPENAI_API_KEY`
- 선택 설정: `OPENAI_EMBEDDING_MODEL`, `CHROMA_*`

`MYSQL_DATABASE`는 TourAPI와 AIHub가 함께 사용하는 단일 데이터베이스입니다.
TourAPI 테이블과 `aihub_` 테이블의 이름은 겹치지 않으며 장소 매핑 테이블은
두 데이터의 관계를 같은 DB 안에서 참조합니다.

인증정보가 담긴 `.env`는 Git에 커밋하지 않습니다.

## 실행 순서

모든 명령은 저장소 루트에서 실행합니다.

```powershell
# 1. LCLS 코드 갱신이 필요할 때만 실행
python -m scripts.crawler.fetch_lcls_codes

# 2. API 호출 없이 현재 수집 상태 확인
python -m scripts.crawler.crawl_products --plan-only

# 3. TourAPI 수집 및 완료 후 RAG JSON 생성
python -m scripts.crawler.crawl_products --call-budget 1000 --checkpoint-every 10

# 4. 기존 CSV로 전처리만 다시 실행할 때 사용
python -m scripts.preprocessing.preprocess_tourapi

# 5. MySQL 스키마 생성 및 데이터 적재
python -m scripts.storage.manage_tourapi_storage mysql-load

# 6. 입력 검증 후 임베딩·ChromaDB 적재
python -m scripts.indexing.build_tourapi_vector_index --dry-run
python -m scripts.indexing.build_tourapi_vector_index --prune
```

`--recreate`는 컬렉션을 삭제하고 전체 임베딩을 다시 생성하므로 OpenAI 비용이
재발생합니다. 입력에서 제거된 문서만 정리하려면 `--prune`을 사용합니다.
공용 MySQL 데이터베이스 전체를 삭제하고 다시 만들 때만
`mysql-load --recreate-database`를 사용합니다. 이 옵션은 같은 DB의 AIHub
테이블도 함께 삭제하므로 이후 AIHub 적재와 매핑을 다시 실행해야 합니다.

## 검증

```powershell
python -B -m unittest discover -s tests/tourapi -p "test_*.py"
python -m scripts.crawler.crawl_products --plan-only
python -m scripts.indexing.build_tourapi_vector_index --dry-run
```

구조 이전 후 TourAPI 테스트 41개와 벡터 입력 dry-run이 통과했습니다.
실제 TourAPI, MySQL, OpenAI 호출은 유효한 인증정보와 외부 서비스 연결이
있어야 최종 확인할 수 있습니다.

## 관련 문서

- [TourAPI 호출과 재시도 정책](api.md)
- [원본·RAG·MySQL·Chroma 데이터 구조](data_schema.md)
- [파이프라인 정리 및 검증 기록](SIMreadme.md)
- [AIHub 전처리·매핑 파이프라인](../aihub/README.md)
