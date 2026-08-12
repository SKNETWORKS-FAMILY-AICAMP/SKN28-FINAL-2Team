# Chroma/RAG 운영 구성

운영 Chroma는 backend task 내부 파일이 아니라 **별도 private ECS Fargate 서비스**로
운영한다. 애플리케이션과 인덱싱 task는 모두 같은 HTTP endpoint와
`jeju_places` 컬렉션을 사용한다.

## 확정 구성

| 항목 | 운영 값 |
| --- | --- |
| 이미지 | `chromadb/chroma:1.5.9` 고정 |
| ECS desired/min/max | `1 / 1 / 1` |
| 네트워크 | private subnet, public IP 없음 |
| 서비스 검색 | AWS Cloud Map private DNS, 예: `chroma.tamrajeju.local` |
| 포트 | TCP 8000, backend/deployment task SG에서만 inbound 허용 |
| 영속 저장소 | 암호화 EFS access point를 컨테이너 `/data`에 mount |
| 백업 | AWS Backup 일 1회, 30일 보존 |
| 로그 | CloudWatch Logs 30일 보존 |

Chroma 자체 인증 없이 private DNS와 security group으로 격리한다. EFS는 전송 중
암호화를 켜고, Chroma task definition의 EFS authorization을 활성화한다. SQLite
기반 저장소를 여러 writer가 공유하지 않도록 Chroma task 수는 반드시 1개로 둔다.

backend와 배포 one-off task의 환경변수는 다음으로 고정한다.

```dotenv
CHROMA_MODE=http
CHROMA_HOST=chroma.tamrajeju.local
CHROMA_PORT=8000
CHROMA_SSL=false
CHROMA_COLLECTION=jeju_places
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`OPENAI_API_KEY`는 Secrets Manager에서 주입한다. `CHROMA_MODE=persistent`는 로컬
개발에서만 허용되며 `DJANGO_DEBUG=false`에서는 애플리케이션 시작 전에 거부된다.

## 인덱싱과 배포

RAG 원본은 이미지에 포함되는
`data/processed/jeju_place_rag_documents.json` 하나를 release source of truth로
사용한다. 웹 프로세스 시작 시 인덱싱하지 않는다.

GitHub Actions의 ECS one-off task가 다음 순서를 실행한다.

1. Django migration
2. `python scripts/verify_rds.py`
3. `python -m scripts.indexing.build_tourapi_vector_index --prune`
4. `python scripts/verify_chroma.py`
5. 모두 성공한 경우에만 backend ECS service 갱신

인덱서는 document hash가 같은 레코드는 다시 embedding하지 않는다. `--prune`은
release JSON에서 제거된 문서만 Chroma에서 제거한다. 비용이 다시 발생하고 기존
컬렉션을 삭제하는 `--recreate`는 자동 배포에서 사용하지 않는다.

최초 구축이나 수동 복구에서도 같은 두 명령을 실행한다.

```powershell
python -m scripts.indexing.build_tourapi_vector_index --prune
python scripts/verify_chroma.py
```

검증은 Chroma heartbeat, 컬렉션 존재 여부, 레코드 수, embedding model/dimension,
전처리·스키마 버전과 release JSON의 일치를 확인하며 실패 시 종료 코드 1을 반환한다.

## 상태 확인과 장애 처리

- `/health/`: Django 프로세스 liveness만 확인하며 ALB health check에 사용
- `/ready/`: account DB, travel DB, Chroma 컬렉션을 확인하며 배포 smoke test에 사용

```powershell
Invoke-RestMethod https://api.example.com/health/
Invoke-RestMethod https://api.example.com/ready/
```

`/ready/`가 503이면 새 배포의 트래픽 전환을 중단한다. Chroma 데이터 손상 시 EFS를
마지막 정상 recovery point로 복원하고 `verify_chroma.py`를 실행한다. 복원이 불가능하면
빈 EFS에서 증분 인덱싱 명령을 실행해 release JSON으로 컬렉션을 재생성한다.

이 구성은 단일 Chroma writer라는 한계가 있다. Chroma 자체 HA나 수평 쓰기 확장이
필요해질 때만 관리형 벡터 DB 또는 Chroma의 HA 지원 배포 방식으로 전환한다.
