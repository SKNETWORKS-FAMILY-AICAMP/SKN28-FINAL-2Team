# RAG Docker 실행 안내

이 구성은 `backend/`와 연결하지 않고 다음 세 구성요소만 실행합니다.

- `mysql`: TourAPI 장소와 AIHub 여행 패턴 정형 데이터
- `rag-init`: 빈 DB·Chroma 볼륨을 자동 초기화하는 1회성 작업
- `rag-ui`: `src/rag`를 직접 호출하는 Streamlit 테스트 UI

ChromaDB는 별도 서버가 아니라 현재 로컬 실행과 동일한 persistent 모드로
`rag_chroma_data` Docker 볼륨에 저장됩니다.

## 1. 사전 준비

Docker Desktop을 실행한 뒤 프로젝트 루트의 `.env`에 최소한 다음 값이 있어야
합니다.

```env
MYSQL_USER=tour_app
MYSQL_PASSWORD=사용할_비밀번호
MYSQL_DATABASE=tour_recommender

OPENAI_API_KEY=...
OPENAI_CHAT_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

KAKAO_REST_API_KEY=...
KAKAO_MOBILITY_ENABLED=true
```

`.env`는 Docker 이미지에 복사되지 않고 실행 시 컨테이너 환경변수로만
전달됩니다. MySQL 컨테이너의 개발용 root 비밀번호도 현재
`MYSQL_PASSWORD`를 사용합니다.

## 2. 최초 실행

프로젝트 루트에서 실행합니다.

```powershell
docker compose -f compose.rag.yaml up --build
```

최초 실행에서는 다음 작업이 자동 수행됩니다.

1. MySQL 8.4 시작
2. TourAPI 테이블 생성 및 장소 적재
3. AIHub 테이블 생성 및 전처리 CSV 적재
4. TourAPI 문서 임베딩 및 Chroma 컬렉션 생성
5. 초기화 완료 후 Streamlit 시작

첫 Chroma 생성은 OpenAI Embeddings API를 호출하므로 시간과 API 비용이
발생합니다. 이후 실행에서는 Docker 볼륨을 재사용하며 변경되지 않은 문서는
다시 임베딩하지 않습니다.

접속 주소:

```text
http://localhost:8501
```

호스트 MySQL은 기존 로컬 MySQL과 충돌하지 않도록 기본적으로 `3307` 포트에
노출됩니다.

## 3. 백그라운드 실행

```powershell
docker compose -f compose.rag.yaml up --build -d
docker compose -f compose.rag.yaml ps
docker compose -f compose.rag.yaml logs -f rag-init rag-ui
```

## 4. 통합 상태점검

TourAPI·AIHub MySQL 테이블과 Chroma 문서 수를 확인합니다.

```powershell
docker compose -f compose.rag.yaml --profile tools run --rm rag-health
```

정상 예시:

```json
{
  "status": "ok",
  "mysql": {
    "places": 2124,
    "place_search_documents": 2102,
    "aihub_travel": 1681,
    "aihub_visit": 31401
  },
  "chroma": {
    "collection": "jeju_places",
    "documents": 2102
  }
}
```

행 수는 데이터 버전에 따라 달라질 수 있습니다.

## 5. 종료와 재시작

컨테이너만 종료하며 DB·Chroma 데이터는 보존합니다.

```powershell
docker compose -f compose.rag.yaml down
```

다시 실행:

```powershell
docker compose -f compose.rag.yaml up -d
```

## 6. 강제 데이터 갱신

MySQL 원본을 다시 적재하려면 `.env`에서 다음 값을 일시적으로 설정합니다.

```env
RAG_DOCKER_FORCE_MYSQL_INIT=true
```

Chroma 컬렉션을 완전히 재생성하려면 다음을 설정합니다. 이 작업은 전체 문서를
다시 임베딩하므로 API 비용이 발생합니다.

```env
RAG_DOCKER_REBUILD_CHROMA=true
```

재생성 후 두 값은 다시 `false`로 되돌립니다.

## 7. 볼륨까지 완전히 초기화

다음 명령은 Docker 안의 MySQL과 Chroma 데이터를 모두 삭제합니다.

```powershell
docker compose -f compose.rag.yaml down -v
```

다음 실행에서는 전체 DB 적재와 임베딩 생성이 다시 진행되므로 정말 초기화가
필요할 때만 사용합니다.

## 주요 파일

- `Dockerfile.rag`: RAG Python 이미지
- `compose.rag.yaml`: MySQL·초기화·Streamlit 구성
- `docker/rag_bootstrap.py`: DB·Chroma 초기화
- `docker/rag_healthcheck.py`: 통합 상태점검
- `.dockerignore`: 비밀키·백엔드·불필요 파일 이미지 제외
