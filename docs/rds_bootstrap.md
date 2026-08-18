# RDS 초기 적재와 운영 검증

이 절차는 MySQL 8.4 RDS의 두 논리 DB를 대상으로 한다.

- `ACCOUNT_DB_NAME`: Django 사용자, 일정, 예약 데이터
- `TRAVEL_DB_NAME` = `MYSQL_DATABASE`: TourAPI, AIHub, 패키지 카탈로그

RDS master 계정은 초기 DB/사용자 생성에만 사용하고 ECS 환경변수나 Secrets
Manager에는 넣지 않는다. 모든 명령은 RDS snapshot을 만든 뒤, RDS에 접근 가능한
SSM 세션·bastion·VPN 환경에서 실행한다.

## 1. 운영 환경변수 준비

ECS task definition의 일반 환경변수와 Secrets Manager 값에 다음 항목을 넣는다.
`scripts/verify_rds.py`는 값을 출력하지 않고 누락·형식만 검사한다.

| 구분 | 이름 |
| --- | --- |
| Django | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `ALLOWED_HOSTS` |
| 브라우저 보안 | `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` (모두 `https://`) |
| 쿠키/HTTPS | `SECURE_SSL_REDIRECT=true`, `SESSION_COOKIE_SECURE=true`, `CSRF_COOKIE_SECURE=true` |
| RDS | `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `ACCOUNT_DB_NAME` |
| 공유 카탈로그 | `TRAVEL_DB_NAME`, `MYSQL_DATABASE` (두 값이 반드시 같아야 함) |
| RAG/LLM | `OPENAI_API_KEY`, `CHROMA_MODE`와 모드별 Chroma 설정 |

ECS에서는 여러 task가 동일한 인덱스를 보도록 `CHROMA_MODE=http`만 사용한다.
`CHROMA_HOST`, `CHROMA_PORT`가 필요하며 상세 구성은
[`chroma_production.md`](chroma_production.md)를 따른다.

DB 접속 전 검증:

```powershell
python scripts/verify_rds.py --environment-only
```

`status: ok`가 아니면 이후 절차를 진행하지 않는다. Django 자체 배포 점검도 함께
실행한다.

```powershell
python backend/manage.py check --deploy --fail-level ERROR
```

## 2. RDS DB와 애플리케이션 사용자 생성

아래 이름과 비밀번호를 실제 값으로 바꾸고 RDS master 계정으로 한 번만 실행한다.
RDS 인스턴스는 public access를 끄고, 3306 inbound는 ECS와 작업용 보안 그룹에만
허용한다.

```sql
CREATE DATABASE `tamrajeju_accounts`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE `tamrajeju_travel`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE USER 'tamrajeju_app'@'%' IDENTIFIED BY 'REPLACE_WITH_SECRET';
GRANT ALL PRIVILEGES ON `tamrajeju_accounts`.* TO 'tamrajeju_app'@'%';
GRANT ALL PRIVILEGES ON `tamrajeju_travel`.* TO 'tamrajeju_app'@'%';
```

위 이름을 각각 `ACCOUNT_DB_NAME`, `TRAVEL_DB_NAME`과 `MYSQL_DATABASE`에 반영한다.
일상 운영에서는 master 계정을 사용하지 않는다.

## 3. 입력 파일 사전 확인

다음 파일이 배포 작업 환경에 있어야 한다.

- `data/raw/korea_tour_openapi_jeju_places.csv`
- `data/processed/jeju_place_rag_documents.json`
- `data/processed/aihub/data/*.csv`, `data/processed/aihub/code/*.csv`
- `src/storage/seed/package_seed.sql`

AIHub CSV의 헤더와 행 수를 DB 접속 없이 먼저 검사한다.

```powershell
python -m scripts.storage.load_aihub_to_mysql --dry-run
```

## 4. 최초 적재

순서를 바꾸지 않는다. 특히 패키지 일정은 `places`를 FK로 참조하므로 TourAPI
적재보다 먼저 실행할 수 없다.

```powershell
# 1) 계정 DB: Django 테이블과 0013 FK 제거 마이그레이션
python backend/manage.py migrate --database=default --noinput
python backend/manage.py migrate --database=default --check

# 2) 공유 DB: TourAPI 장소와 RAG 검색 문서
python -m scripts.storage.manage_tourapi_storage mysql-load

# 3) 공유 DB: AIHub 원천 테이블 (최초에는 --replace 금지)
python -m scripts.storage.load_aihub_to_mysql
```

운영 RDS 초기 적재에서는 AIHub와 TourAPI 장소 매핑을 실행하지 않는다.
`scripts.preprocessing.map_aihub_places`와 관련 코드는 향후 검토를 위해 유지하지만,
별도 결정 전까지 운영 적재 절차에는 포함하지 않는다.

패키지 seed는 mysqldump라 `travel_packages`, `package_items`를 `DROP`한다. 아래
사전 확인 결과가 **0행일 때 최초 1회만** 실행한다. 한 행이라도 나오면 중단하고
기존 데이터 보존/병합 방법을 먼저 결정한다.

```sql
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'tamrajeju_travel'
  AND TABLE_NAME IN ('travel_packages', 'package_items');
```

빈 DB임을 확인한 뒤 안전 실행기를 사용한다. 이 실행기는 대상 테이블이 이미 있으면
중단하고, seed가 참조하는 모든 장소가 `places`에 존재하는지도 먼저 확인한다.

```powershell
python -m scripts.storage.load_package_seed --confirm-empty-database
```

`--recreate-database`, AIHub `--replace`, 패키지 seed 재실행은 운영 자동 배포에 넣지
않는다. 이들은 기존 데이터를 삭제하거나 교체할 수 있다.

## 5. 적재 결과 자동 검증

전체 적재 후 애플리케이션 권한으로 실행한다.

```powershell
python scripts/verify_rds.py
```

검증기는 다음 항목 중 하나라도 실패하면 종료 코드 1을 반환한다.

- 두 DB의 필수 테이블 존재 여부
- Django migration, 장소, RAG 문서, 패키지, AIHub 원천 데이터가 비어 있지 않은지
- 패키지 항목의 장소/패키지 orphan 여부
- AIHub 방문의 여행 orphan 여부
- `travel_itinerary.selected_package_id`에 cross-database FK가 남아 있지 않은지
- `0013_remove_cross_database_package_fk` 적용 여부

최종적으로 `/health/` ALB health check와 실제 로그인 → 추천 → 일정 저장 smoke test까지
통과한 뒤 ECS 트래픽을 전환한다. RDS 초기 적재는 CI/CD마다 반복하지 않고, 이후
스키마 변경은 Django migration과 별도의 버전 관리된 catalog migration으로 처리한다.

`migrate_package_companion_tags_50.sql`은 배포 준비 태스크에서
`python -m scripts.storage.migrate_package_catalog`로 한 번만 적용되며, 적용 이력과
체크섬은 `tourmain_catalog_migrations`에 기록된다.
