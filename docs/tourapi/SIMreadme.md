# 데이터 파이프라인 정리 및 검증 기록

이 문서는 TourAPI와 AIHub 데이터 파이프라인을 새 `main` 저장소 구조로
이전하면서 확정한 범위와 검증 결과를 기록합니다. 실행 방법은
[TourAPI README](README.md)와 [AIHub README](../aihub/README.md)를 기준으로
합니다.

## 유지한 기능

- TourAPI LCLS 및 제주 장소 수집
- TourAPI 원본 CSV 체크포인트와 재개
- TourAPI 장소 정제·분류·중복 병합
- TourAPI MySQL 스키마 생성과 적재
- OpenAI 임베딩과 TourAPI ChromaDB 적재
- AIHub 제주 데이터 전처리와 MySQL 적재
- AIHub 장소 그룹화와 TourAPI 비교·매핑
- 파이프라인 설명 문서와 단위·통합 테스트

AIHub용 임베딩 및 벡터 DB 생성 코드는 범위에서 제외했습니다.

## 구조 원칙

- `data/raw/`: 원본 또는 다시 수집할 수 있는 입력
- `data/processed/`: 전처리·매핑 산출물
- Docker `chroma-data` volume: 기본 HTTP 모드 TourAPI ChromaDB
- `data/vectorstore/`: persistent 모드 ChromaDB와 manifest
- `scripts/`: 사용자가 실행하는 명령
- `src/`: 재사용 가능한 도메인·저장소·임베딩 로직
- `tests/`: TourAPI와 AIHub 파이프라인 검증
- `docs/`: 실행 방법, 데이터 구조, 검증 기록

루트 `README.md`는 저장소 정책에 따라 빈 파일로 유지하고, 데이터 파이프라인
문서는 `docs/` 아래에서 관리합니다.

MySQL은 `.env`의 `MYSQL_DATABASE` 하나만 생성·사용합니다. TourAPI 테이블과 AIHub `aihub_` 테이블을 같은 DB에 적재해야 `aihub_places`와 `places` 사이의 매핑 외래키와 무결성 검증이 동작합니다.

## 현재 기준 데이터

| 항목 | 현재 값 |
| --- | ---: |
| TourAPI 원본 장소 | 2,124 |
| TourAPI RAG 문서 | 2,102 |
| TourAPI 숙소 RAG 문서 | 236 |
| TourAPI 전처리 버전 | `places-v5` |
| Chroma 컬렉션 | `jeju_places` |
| AIHub MySQL 대상 테이블 | 13 |
| AIHub MySQL 대상 행 | 141,322 |

기본 Docker 환경의 ChromaDB 파일은 `chroma-data` named volume의 `/data`에
저장하며 Git에 포함하지 않습니다. `CHROMA_MODE=persistent`를 사용하는 경우에만
실제 파일이 `data/vectorstore/`에 생성됩니다. 어느 모드든 manifest의 입력
해시와 문서 수가 현재 RAG JSON과 일치하는지 배포 전에 확인해야 합니다.

## 최종 검증

2026-07-27 Docker 로컬 검증 결과:

- MySQL `places` 2,124건 실제 적재
- ChromaDB `jeju_places` 2,102건 실제 적재
- MySQL RAG 대상 ID와 Chroma ID 2,102건 완전 일치
- 저장 벡터 최근접 검색과 MySQL 상세정보 연결 통과
- AIHub 13개 테이블 총 141,322행 실제 적재
- AIHub 장소 7,642개 생성, TourAPI 자동 매칭 722개
- AIHub Mock 테스트 33개와 실제 DB 통합 테스트 1개 통과
- 적재·매핑 무결성 오류 0건

dry-run은 입력 파일과 실행 경로를 검증하지만 실제 외부 연결을 대신하지
않습니다. 운영 전에는 별도로 TourAPI 인증, MySQL 연결, OpenAI 임베딩 호출을
확인해야 합니다.

## 남은 운영 과제

- 현재 저장된 LCLS 코드의 깊이를 확인하고 필요하면 기본 depth 3으로 갱신
- 현재 브랜치에서 삭제된 `src.rag` 구현과 RAG 통합 테스트 복구
- DB·벡터 교차 검증을 반복 가능한 통합 테스트로 추가
- 테스트와 두 dry-run을 GitHub Actions에 추가
- AWS에서는 RDS MySQL과 private Chroma 호스트로 분리하고 Secrets Manager 적용
