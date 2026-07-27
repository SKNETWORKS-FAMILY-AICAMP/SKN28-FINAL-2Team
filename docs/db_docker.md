# Docker 로컬 DB 개발 환경

이 문서는 프로젝트의 MySQL과 ChromaDB를 Docker로 실행하고, TourAPI·AIHub
데이터와 임베딩 벡터를 적재한 뒤 로컬 VS Code 코드에서 사용하는 방법을
설명합니다. 모든 명령은 Windows PowerShell과 저장소 루트를 기준으로 합니다.

## 현재 범위

현재 Docker화된 대상은 로컬 개발용 DB 인프라입니다.

```text
로컬 VS Code Python
├─ 127.0.0.1:13306 → Docker MySQL:3306
└─ 127.0.0.1:8000  → Docker ChromaDB:8000
```

백엔드, AI API, 프론트엔드는 아직 컨테이너로 실행하지 않습니다. 현재 브랜치에는
`src.rag` 공개 API가 참조하는 구현 파일도 없으므로, 이 문서에서는 DB 연결과
벡터 저장소 자체를 검증합니다.

## 사용하는 공식 이미지

### MySQL

- 이미지: `mysql:8.4`
- 이미지 기본 실행: `docker-entrypoint.sh` 이후 `mysqld`
- 내부 포트: `3306`, `33060`
- 기본 데이터 경로: `/var/lib/mysql`
- 초기화 파일 경로: `/docker-entrypoint-initdb.d/`

공식 이미지는 빈 데이터 디렉터리로 처음 실행할 때 `MYSQL_*` 환경변수로
관리자 비밀번호, 데이터베이스, 일반 사용자를 준비하고 초기화 디렉터리의
스크립트를 이름순으로 실행합니다. 프로젝트 데이터는 공식 이미지에 들어 있지
않습니다.

프로젝트 `compose.yaml`은 공식 이미지에 다음 설정을 추가합니다.

- 호스트 포트 `127.0.0.1:13306`
- `utf8mb4`, `utf8mb4_0900_ai_ci`
- `mysql-data` named volume
- TourAPI → AIHub → 장소 매핑 순서의 스키마 SQL
- MySQL healthcheck

### ChromaDB

- 이미지: `chromadb/chroma:1.5.9`
- 이미지 기본 실행: `dumb-init -- chroma run /config.yaml`
- 내부 HTTP 포트: `8000`
- 기본 persist 경로: `/data`

공식 이미지의 기본 `/config.yaml`은 `persist_path: "/data"`를 지정합니다.
기본 이미지에는 프로젝트 컬렉션, 인증, HTTPS, 백업, healthcheck가 없습니다.

프로젝트 `compose.yaml`은 공식 이미지에 다음 설정을 추가합니다.

- 호스트 포트 `127.0.0.1:8000`
- `/data`에 연결하는 `chroma-data` named volume
- Chroma 포트 healthcheck

두 포트 모두 `127.0.0.1`에만 bind하므로 현재 PC 외부에서 직접 접속할 수
없습니다.

## 사전 준비

필요한 프로그램은 다음과 같습니다.

- Docker Desktop
- Docker Compose
- Python
- Git

설치 확인:

```powershell
docker --version
docker compose version
python --version
```

저장소 루트로 이동하고 Python 의존성을 설치합니다.

```powershell
Set-Location "C:\path\to\SKN28-final-2TEAM-main"
python -m pip install -r requirements.txt
```

`docker compose`는 현재 디렉터리에서 `compose.yaml`을 찾습니다. 다른
디렉터리, 특히 `C:\WINDOWS\System32`에서 실행하면
`no configuration file provided` 오류가 발생합니다.

## 환경변수 준비

예시 파일을 복사합니다.

```powershell
Copy-Item .env.example .env
```

최소한 다음 값을 로컬 `.env`에 설정합니다.

```dotenv
MYSQL_ROOT_PASSWORD=로컬에서_사용할_관리자_비밀번호
MYSQL_HOST=127.0.0.1
MYSQL_PORT=13306
MYSQL_USER=tour_app
MYSQL_PASSWORD=로컬에서_사용할_앱_비밀번호
MYSQL_DATABASE=tour_recommender

CHROMA_MODE=http
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8000
CHROMA_SSL=false

OPENAI_API_KEY=본인의_API_키
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`MYSQL_ROOT_PASSWORD`는 Docker MySQL 내부에 새 관리자 계정을 만드는 데
사용합니다. PC에 이미 설치된 MySQL의 root 계정을 재사용하지 않습니다.
`OPENAI_API_KEY`는 벡터 생성과 자연어 검색어 임베딩에만 필요합니다.

`.env`는 Git에 포함하지 않습니다. 실제 비밀번호와 API 키를
`.env.example`, 문서, 소스 코드에 기록하지 않습니다.

## DB 컨테이너 실행

Compose 설정을 검증하고 서비스를 실행합니다.

```powershell
docker compose config --quiet
docker compose up -d
docker compose ps
```

정상 상태의 핵심 표시는 다음과 같습니다.

```text
mysql       running (healthy)   127.0.0.1:13306->3306
chromadb    running (healthy)   127.0.0.1:8000->8000
```

이미지 확인:

```powershell
docker image ls mysql
docker image ls chromadb/chroma
```

## 최초 데이터 적재

### 1. TourAPI MySQL 적재

```powershell
python -m scripts.storage.manage_tourapi_storage mysql-load
```

원본 CSV와 RAG JSON을 읽어 TourAPI 테이블에 적재합니다.

### 2. AIHub 입력 검증과 MySQL 적재

```powershell
python -m scripts.storage.load_aihub_to_mysql --dry-run
python -m scripts.storage.load_aihub_to_mysql
```

첫 번째 명령은 DB에 쓰지 않고 CSV 컬럼, 파일 구성, 행 수만 검증합니다.
두 번째 명령이 TourAPI와 같은 `MYSQL_DATABASE`의 `aihub_` 테이블에 실제
데이터를 적재합니다.

이미 AIHub 데이터가 있는 DB를 의도적으로 다시 적재할 때만 다음 명령을
사용합니다.

```powershell
python -m scripts.storage.load_aihub_to_mysql --replace
```

`--replace`는 AIHub 테이블의 기존 행을 삭제한 뒤 다시 적재합니다.

### 3. AIHub 장소와 TourAPI 장소 매핑

```powershell
python -m scripts.preprocessing.map_aihub_places
```

AIHub 방문 기록을 장소 단위로 그룹화하고 이름·주소·좌표를 비교해
`aihub_places.tourapi_content_id`에 TourAPI 장소 관계를 저장합니다.

### 4. ChromaDB 벡터 적재

먼저 입력만 검증합니다.

```powershell
python -m scripts.indexing.build_tourapi_vector_index --dry-run
```

실제 임베딩과 Chroma 적재:

```powershell
python -m scripts.indexing.build_tourapi_vector_index --prune
```

이 명령은 OpenAI 임베딩 API 비용을 발생시킵니다. 문서 해시, 모델, 차원이
같은 기존 벡터는 건너뜁니다. `--prune`은 현재 입력에서 제거된 오래된 문서를
컬렉션에서 정리합니다.

다음 옵션은 컬렉션을 삭제하고 전체 임베딩을 다시 만들기 때문에 모델이나
차원을 변경할 때만 사용합니다.

```powershell
python -m scripts.indexing.build_tourapi_vector_index --recreate
```

## 적재와 연결 확인

### 컨테이너 상태와 로그

```powershell
docker compose ps
docker compose logs --tail=50 mysql
docker compose logs --tail=50 chromadb
```

### MySQL 확인

```powershell
docker compose exec mysql mysql -u root -p
```

`MYSQL_ROOT_PASSWORD`를 입력한 뒤 다음 SQL을 실행합니다.

```sql
USE tour_recommender;

SELECT COUNT(*) FROM places;
SELECT COUNT(*) FROM place_search_documents WHERE rag_eligible = TRUE;
SELECT COUNT(*) FROM aihub_travel;
SELECT COUNT(*) FROM aihub_visit;
SELECT match_status, COUNT(*) FROM aihub_places GROUP BY match_status;

EXIT;
```

### ChromaDB 확인

서버 응답:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v2/heartbeat
```

컬렉션 건수:

```powershell
python -c "import chromadb; c=chromadb.HttpClient(host='127.0.0.1', port=8000); col=c.get_collection('jeju_places'); print(col.count())"
```

저장된 문서 일부:

```powershell
python -c "import chromadb; c=chromadb.HttpClient(host='127.0.0.1', port=8000); col=c.get_collection('jeju_places'); print(col.peek(3))"
```

### 현재 제공되는 테스트

임베딩 인덱서의 HTTP·persistent 모드:

```powershell
python -B -m unittest tests.test_embeddings_cli -v
```

AIHub Mock 기반 로직:

```powershell
python -B -m unittest tests.aihub.test_aihub_similarity -v
```

실제 MySQL AIHub 통합 테스트:

```powershell
$env:RUN_AIHUB_DB_INTEGRATION='1'
python -B -m unittest tests.aihub.test_aihub_similarity_integration -v
Remove-Item Env:RUN_AIHUB_DB_INTEGRATION
```

현재 브랜치에는 `tests/rag/test_place_search.py`와 이를 실행하는 `src.rag`
구현이 없습니다. 따라서 최종 자연어 RAG 서비스 API 테스트는 구현을 복구한
뒤 추가해야 합니다.

## VS Code 로컬 코드에서 접속

로컬 Python은 DB 파일을 직접 열지 않고 주소와 포트를 통해 실행 중인 DB
프로세스에 요청합니다. 데이터는 Docker volume에 남고 조회 결과만 Python
프로세스로 반환됩니다.

MySQL은 프로젝트의 `MySQLConfig.from_env()`를 사용합니다.

```python
from src.common.env import load_env_file
from src.config.settings import MySQLConfig

load_env_file(".env")
config = MySQLConfig.from_env()
```

ChromaDB는 HTTP client로 접속합니다.

```python
import chromadb

client = chromadb.HttpClient(
    host="127.0.0.1",
    port=8000,
)
collection = client.get_collection("jeju_places")
```

나중에 백엔드와 AI API도 같은 Compose 네트워크에서 실행하면 localhost 대신
서비스 이름과 내부 포트를 사용합니다.

```dotenv
MYSQL_HOST=mysql
MYSQL_PORT=3306
CHROMA_HOST=chromadb
CHROMA_PORT=8000
```

## 시작, 종료, 데이터 유지

서비스 중지와 재시작:

```powershell
docker compose stop
docker compose start
```

컨테이너와 네트워크만 제거:

```powershell
docker compose down
```

named volume은 남으므로 다시 실행하면 데이터가 유지됩니다.

다음 명령은 컨테이너와 MySQL·Chroma volume 데이터를 모두 삭제합니다.

```powershell
docker compose down -v
```

초기화를 명확히 의도한 경우가 아니라면 `-v`를 사용하지 않습니다.
MySQL 공식 이미지의 환경변수와 초기 SQL도 빈 `mysql-data` volume의 최초
실행 때만 적용됩니다.

## Git과 팀 공유 범위

Git에 포함할 파일:

- `compose.yaml`
- `.env.example`
- `.gitignore`
- 스키마와 적재 스크립트
- 전처리 데이터 중 저장소 정책상 공유 가능한 파일
- 테스트와 이 문서

Git에 포함하지 않을 항목:

- `.env`, `.env.local` 등 비밀정보
- `mysql-data`, `chroma-data` Docker volume
- 로컬 Chroma 실제 파일
- 로컬 DB dump와 backup
- AIHub 원본

팀원은 저장소를 clone한 뒤 각자 `.env`를 만들고 컨테이너를 실행해야 합니다.
Docker volume은 Git으로 전달되지 않으므로 최초 데이터 적재도 각 환경에서
수행합니다. 벡터를 매번 새로 임베딩하지 않게 하려면 검증된 MySQL dump와
Chroma backup을 Git이 아닌 S3 같은 별도 저장소로 배포하고 복원 스크립트를
제공해야 합니다. 원본·가공 데이터의 외부 공유가 허용되는지도 라이선스를
먼저 확인합니다.

## 자주 발생하는 오류

### Compose 파일을 찾지 못함

```text
no configuration file provided: not found
```

저장소 루트로 이동한 뒤 다시 실행합니다.

```powershell
Set-Location "C:\path\to\SKN28-final-2TEAM-main"
docker compose up -d
```

### 포트 바인딩 실패

Windows 환경에서 호스트 `3306` 포트를 bind하지 못해 프로젝트는 호스트
포트 `13306`을 사용합니다. 컨테이너 내부 MySQL 포트는 계속 `3306`입니다.

```powershell
Get-NetTCPConnection -State Listen -LocalPort 13306
```

### 컨테이너가 unhealthy

```powershell
docker compose ps
docker compose logs --tail=100 mysql
docker compose logs --tail=100 chromadb
```

환경변수 누락, 기존 volume의 잘못된 초기화, 포트 충돌을 확인합니다.

### 환경변수를 바꿨지만 MySQL에 적용되지 않음

`MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`는
빈 데이터 디렉터리를 초기화할 때 사용합니다. 기존 `mysql-data` volume에는
변경된 값이 자동 적용되지 않습니다. 운영 데이터가 있는 경우 volume을
삭제하지 말고 관리자 계정으로 접속해 SQL로 계정과 권한을 변경합니다.

## 현재 검증 기준

2026-07-27 로컬 Docker 환경에서 확인한 값입니다.

| 항목 | 건수 |
| --- | ---: |
| TourAPI 원본 장소 | 2,124 |
| MySQL RAG 대상 | 2,102 |
| Chroma `jeju_places` | 2,102 |
| AIHub 여행 | 1,681 |
| AIHub 방문 | 31,401 |
| AIHub 장소 | 7,642 |
| TourAPI 자동 매칭 | 722 |

MySQL RAG 대상 ID와 `tourapi:` 접두사를 제거한 Chroma ID가 2,102건 모두
일치했습니다. 저장된 벡터 최근접 검색 결과의 ID로 MySQL 장소 상세정보를
정상 조회했습니다. AIHub Mock 테스트 33개, 실제 DB 통합 테스트 1개,
임베딩 모드 테스트 2개가 통과했습니다.

## AWS 이전 시 달라지는 점

로컬 Compose 설정을 그대로 운영 DB로 공개하지 않습니다.

- MySQL은 Amazon RDS for MySQL로 이전
- ChromaDB는 private EC2와 EBS 등에 배치
- 백엔드·AI API Docker 이미지는 ECR과 ECS에서 실행
- DB 주소와 포트를 RDS endpoint와 private Chroma 주소로 변경
- 관리자·서비스·개발자 DB 계정을 분리
- 애플리케이션은 관리자 계정 대신 최소 권한 서비스 계정 사용
- 비밀번호와 API 키는 AWS Secrets Manager에 저장
- RDS와 Chroma 포트는 인터넷에 공개하지 않음
- 최초 데이터 적재와 코드 배포를 분리
- 이후 스키마 변경은 배포 시 DB 초기화가 아니라 migration으로 관리

현재 `compose.yaml`은 팀원 로컬 개발환경 재현을 위한 설정입니다.
