# AWS 배포 인수인계

마지막 확인: 2026-08-12 (Asia/Seoul)

이 문서는 새 Codex 작업이나 팀원이 현재 운영 배포 상태를 이어서 작업하기 위한 기준 문서다.
AWS·Terraform·CI/CD 작업을 시작하기 전에 이 문서와 실제 코드, Terraform plan, AWS 읽기 전용
조회 결과를 함께 확인한다. 이 문서에 비밀번호, API 키, SecretString은 기록하지 않는다.

## 1. 현재 결론

- 기초 운영 배포는 완료됐다.
- 프론트엔드는 CloudFront와 비공개 S3에서 제공된다.
- 백엔드와 Chroma는 ECS Fargate 서비스로 각각 1개 task가 실행 중이다.
- RDS MySQL은 private, Single-AZ 구성으로 사용 가능 상태다.
- RDS 스키마 초기화, Django migration, 데이터 검증, Chroma 증분 인덱싱이 완료됐다.
- CloudWatch 대시보드와 8개 알람이 Terraform으로 관리되며 현재 모두 `OK`다.
- GitHub Actions CI/CD 코드는 준비됐지만 운영 배포는 아직 `main`의 수동 실행으로 검증해야 한다.
- Google/Kakao OAuth 운영 도메인 등록과 로그인 이후 전체 사용자 흐름 검증이 남아 있다.

## 2. 로컬 작업 상태

| 항목 | 값 |
| --- | --- |
| 저장소 | `SKNETWORKS-FAMILY-AICAMP/SKN28-FINAL-2Team` |
| 현재 로컬 브랜치 | `sim/merge-all` |
| 확인 당시 HEAD | `54240bb fix: 변경된 패키지에 맞게 코드 수정` |
| AWS CLI profile | `skn28-terraform` |
| AWS account | `511092105773` |
| AWS region | `ap-northeast-2` |
| Terraform state bucket | `tourmain-terraform-state-511092105773` |
| Terraform state key | `production/terraform.tfstate` |

현재 worktree에는 애플리케이션 수정과 배포 수정이 함께 있고 `.github/`, `infra/`, 일부 문서와
스크립트가 아직 untracked로 표시된다. 다른 팀원의 `main`을 합치기 전에 현재 변경을 별도 commit으로
보존하거나 안전한 백업 브랜치에 기록해야 한다. `git reset --hard`, `git checkout -- .` 같은 명령으로
현재 변경을 지우면 안 된다.

## 3. 현재 운영 아키텍처

사용자 요청 흐름은 다음과 같다.

```text
Browser
  -> CloudFront HTTPS
     -> Private S3: React 정적 파일
     -> ALB HTTP: API, health, ready, admin, swagger 경로
        -> ECS Fargate backend
           -> Private RDS MySQL
           -> Cloud Map private DNS
              -> ECS Fargate Chroma
                 -> Encrypted EFS
```

외부 API 호출은 backend task의 public IP와 Internet Gateway를 사용한다. NAT Gateway는 사용하지
않는다. 상세 다이어그램은 다음 파일에 있다.

- `docs/architecture/aws-current.eraserdiagram`
- `docs/architecture/aws-deployment.eraserdiagram`

## 4. 현재 AWS 리소스

### 진입점과 프론트엔드

| 항목 | 현재 값 |
| --- | --- |
| 서비스 URL | `https://d9mejd7qkrml.cloudfront.net` |
| CloudFront distribution | `E19GBBQUW25GVT` |
| CloudFront 상태 | `Deployed`, enabled |
| 프론트 S3 | `tourmain-frontend-511092105773` |
| S3 공개 접근 | 차단됨 |
| S3 접근 방식 | CloudFront Origin Access Control |
| ALB DNS | `tourmain-production-api-1762646320.ap-northeast-2.elb.amazonaws.com` |

CloudFront 기본 동작은 S3로 연결되고 다음 경로는 ALB로 전달된다.

- `/api/*`
- `/health/*`
- `/ready/*`
- `/admin/*`
- `/swagger/*`

CloudFront Function이 React Router 경로를 `index.html`로 재작성한다. 사용자 도메인, Route 53,
ACM 인증서는 아직 사용하지 않고 CloudFront 기본 도메인과 인증서를 사용한다.

### ECS와 이미지

| 항목 | 현재 값 |
| --- | --- |
| ECS cluster | `tourmain-production` |
| Backend service | `tourmain-backend` |
| Backend desired/running | `1 / 1` |
| Backend task definition | `tourmain-prod-backend:8` |
| Chroma service | `tourmain-chroma` |
| Chroma desired/running | `1 / 1` |
| Chroma task definition | `tourmain-prod-chroma:1` |
| ECR repository | `tourmain/backend` |
| Terraform baseline image | `manual-initial-v8` |

2026-08-12 읽기 전용 확인에서 ALB target은 `healthy`, port `8000`이었다.

ECR 정책은 다음과 같다.

- immutable tag
- scan on push
- `manual-initial-*` 최근 2개 유지
- `deploy-*` 최근 10개 유지
- untagged image는 1일 후 제거

### RDS

| 항목 | 현재 값 |
| --- | --- |
| Identifier | `tourmain-mysql` |
| Engine | MySQL `8.4.9` |
| Instance class | `db.t4g.micro` |
| Storage | 20 GiB gp3, 최대 자동 확장 50 GiB |
| Public access | `false` |
| Multi-AZ | `false` |
| 상태 | `available` |
| 백업 보존 | 7일 |
| 삭제 방지 | 활성화 |
| 로그 | error, slow query |

애플리케이션 DB 구성은 다음과 같다.

| 환경변수 | DB |
| --- | --- |
| `ACCOUNT_DB_NAME` | `accounts_db` |
| `TRAVEL_DB_NAME` | `tour_recommender` |
| `MYSQL_DATABASE` | `tour_recommender` |

운영 애플리케이션 계정은 `tour_prod_app`이다. RDS master 계정은 초기 bootstrap에만 사용하고 일반
애플리케이션 task에는 사용하지 않는다. 계정 비밀번호는 Secrets Manager에서만 관리한다.

### Chroma/RAG

| 항목 | 현재 값 |
| --- | --- |
| Chroma image | `chromadb/chroma:1.5.9` |
| 접속 모드 | HTTP |
| Private DNS | `chroma.tamrajeju.local` |
| Port | `8000` |
| Collection | `jeju_places` |
| Embedding model | `text-embedding-3-small` |
| Embedding dimensions | `1536` |
| Storage | encrypted EFS access point |
| Chroma task 수 | 1 |

2026-08-11 마지막 정상 `/ready/` 응답에서 다음 값이 확인됐다.

```json
{
  "status": "ready",
  "databases": "ok",
  "chroma": {
    "collection": "jeju_places",
    "records": 2102,
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 1536,
    "preprocessing_version": "places-v5",
    "schema_version": "1.0"
  }
}
```

2026-08-12 로컬 PowerShell/curl readiness 재호출은 Windows Schannel의 로컬 인증서 오류로 HTTP
요청 전에 실패했다. 같은 시점 AWS 조회에서 CloudFront는 `Deployed`, ALB target은 `healthy`였으므로
이 결과만으로 서버 장애로 판단하지 않는다.

AIHub와 TourAPI 장소 매핑 로직은 코드에 남겨뒀지만 RDS 초기 적재에서는 적용하지 않았다. 운영
데이터 적재 순서는 Django migration, TourAPI 장소/RAG 문서, AIHub 원천 테이블이며 매핑 작업은
별도 결정 전까지 실행하지 않는다.

## 5. 네트워크와 보안

- VPC: `vpc-0ee34cc6074d7f2c2`, CIDR `10.20.0.0/16`
- Public subnet 2개, private subnet 2개, data subnet 2개를 Terraform으로 관리한다.
- Backend와 Chroma task는 현재 public subnet에서 public IP를 받는다.
- ALB port 80 inbound는 AWS 관리형 CloudFront origin-facing prefix list에서만 허용한다.
- ALB에서 backend port 8000은 application security group으로만 허용한다.
- Backend에서 RDS port 3306은 security group 참조로만 허용한다.
- Backend에서 Chroma port 8000은 Chroma security group으로만 허용한다.
- Chroma에서 EFS port 2049는 EFS security group으로만 허용한다.
- RDS는 public access가 비활성화되어 있다.
- Secrets Manager가 Django, MySQL, OpenAI, Google, Kakao 값을 ECS에 주입한다.
- secret value는 Terraform 코드, tfvars, GitHub variable, 문서에 저장하지 않는다.

현재 비용과 기간을 고려해 NAT Gateway, WAF, Container Insights, Auto Scaling, 사용자 도메인은
추가하지 않았다.

## 6. Terraform 관리 상태

Terraform 디렉터리는 `infra/terraform`이다. S3 remote state와 lockfile을 사용한다.

주요 파일:

- `infra/terraform/existing.tf`: 기존 VPC, subnet, SG, RDS, ECR, GitHub OIDC adoption
- `infra/terraform/runtime.tf`: ALB, ECS, Chroma, EFS, Secrets Manager
- `infra/terraform/frontend.tf`: S3, CloudFront, SPA rewrite
- `infra/terraform/monitoring.tf`: SNS, CloudWatch dashboard, alarms
- `infra/terraform/imports.tf`: 기존 리소스 import 선언
- `infra/terraform/variables.tf`: 운영 기본값

Terraform과 CI/CD의 소유권은 다음처럼 분리한다.

- Terraform: 인프라, ECS service, task definition의 baseline 구성
- GitHub Actions: 배포 image로 새 backend task definition revision 생성 및 ECS service 업데이트
- `aws_ecs_service.backend`는 `task_definition` 변경을 ignore하여 Terraform이 CI/CD 배포 revision을
  이전 baseline으로 되돌리지 않게 한다.

마지막 확인된 Terraform output:

```text
backend_task_definition   = tourmain-prod-backend:8
ecs_cluster_name          = tourmain-production
backend_service_name      = tourmain-backend
frontend_bucket           = tourmain-frontend-511092105773
frontend_url              = https://d9mejd7qkrml.cloudfront.net
production_rds_identifier = tourmain-mysql
cloudwatch_dashboard_name = tourmain-production
```

`*.tfplan`은 생성 시점의 state에 고정되는 일회성 파일이다. 오래된 plan을 재사용하지 말고 코드 병합
후 반드시 새 plan을 생성한다. plan에 예상하지 않은 destroy나 replace가 있으면 apply하지 않는다.

## 7. DB와 배포를 위해 수정한 코드

다른 팀원의 코드와 병합할 때 다음 배포 변경을 보존한다.

- Django 다중 DB 설정과 운영 환경변수 검증
- cross-database FK 제거 migration `0013_remove_cross_database_package_fk`
- RDS 필수 테이블과 migration 검증 스크립트
- RDS bootstrap 스크립트와 테스트
- 운영 MySQL connector backend 호환 수정
- `/health/` liveness와 `/ready/` DB/Chroma readiness 분리
- Chroma HTTP 운영 모드와 startup 환경 검증
- RAG 증분 인덱싱 및 Chroma 검증
- Docker image에 migration, 검증, seed에 필요한 파일 포함
- 프론트 API base URL과 OAuth build 환경변수 처리
- AWS Terraform 전체 구성
- GitHub Actions CI/CD workflow

관련 파일:

- `backend/config/settings.py`
- `backend/config/env_validation.py`
- `backend/config/mysql_connector_backend/`
- `backend/apps/travel/migrations/0013_remove_cross_database_package_fk.py`
- `scripts/bootstrap_rds.py`
- `scripts/verify_rds.py`
- `scripts/verify_chroma.py`
- `scripts/storage/load_package_seed.py`
- `backend/Dockerfile`
- `.github/workflows/ci-cd.yml`

상세 절차:

- `docs/rds_bootstrap.md`
- `docs/chroma_production.md`
- `docs/aws_cicd.md`

## 8. 모니터링

CloudWatch dashboard `tourmain-production`과 다음 알람이 Terraform state 및 AWS에 존재한다.
2026-08-12 확인 당시 모두 `OK`였다.

- `tourmain-alb-target-5xx`
- `tourmain-alb-unhealthy-targets`
- `tourmain-ecs-backend-cpu-high`
- `tourmain-ecs-backend-memory-high`
- `tourmain-ecs-chroma-cpu-high`
- `tourmain-ecs-chroma-memory-high`
- `tourmain-mysql-free-storage-low`
- `tourmain-rds-cpu-high`

알람은 SNS topic `tourmain-alerts`로 전달한다. Container Insights와 custom metric은 비용 절감을 위해
사용하지 않는다.

## 9. CI/CD 준비 상태

Workflow: `.github/workflows/ci-cd.yml`

- pull request와 `main` push에서 backend/frontend/container CI가 실행된다.
- 실제 production deploy job은 `main`에서 `workflow_dispatch`로 수동 실행할 때만 동작한다.
- GitHub `production` environment를 사용한다.
- AWS access key 대신 GitHub OIDC와 `tourmain-github-deploy-role`을 사용한다.
- backend image tag는 `deploy-${GITHUB_SHA}`이다.
- 새 task definition으로 one-off migration/RDS/Chroma 검증을 먼저 수행한다.
- 검증 성공 후 ECS service를 갱신한다.
- `/ready/` 실패 시 이전 task definition으로 rollback한다.
- frontend는 `npm ci`, `npm run build`, S3 sync, CloudFront invalidation 순서다.

GitHub `production` environment에 다음 variables가 필요하다.

```text
AWS_REGION
AWS_ROLE_ARN
ECR_REPOSITORY
ECS_CLUSTER
ECS_SERVICE
ECS_CONTAINER_NAME
FRONTEND_S3_BUCKET
CLOUDFRONT_DISTRIBUTION_ID
VITE_API_BASE_URL
VITE_GOOGLE_CLIENT_ID
VITE_KAKAO_JAVASCRIPT_KEY
VITE_KAKAO_REDIRECT_URI
```

CI/CD는 코드만 준비된 상태로 간주한다. `main` 병합 후 첫 workflow를 실행하기 전에 environment
variables, required reviewer, OIDC subject, IAM scope를 확인하고 수동 실행한다.

## 10. 병합 후 Docker 이미지 빌드와 ECR 업로드

### 병합만으로는 운영에 반영되지 않는다

`git merge`와 `git push`는 소스 코드만 변경한다. 현재 실행 중인 AWS 리소스는 다음 작업을 별도로
수행하기 전까지 기존 상태를 유지한다.

| 변경 종류 | 운영 반영에 필요한 작업 |
| --- | --- |
| Backend Python/Django | Docker image 재빌드 → ECR push → 새 task definition → migration/검증 → ECS service 갱신 |
| Django migration | 새 image로 ECS one-off migration task를 먼저 성공시킴 |
| RAG/indexing 코드 또는 문서 | 새 image로 증분 indexing과 `verify_chroma.py` 실행 |
| Frontend React | `npm run build` → S3 sync → CloudFront invalidation |
| Terraform | 새 `terraform plan` 검토 → 승인된 plan apply |
| Secrets Manager 값 | secret 갱신 → 값을 다시 읽도록 새 ECS deployment 실행 |
| Google/Kakao OAuth | 각 provider console에 운영 origin과 redirect URI 등록 |

따라서 병합 후 현재 ECS task가 자동으로 새 코드를 실행한다고 가정하면 안 된다. GitHub Actions
production workflow가 준비되고 검증됐다면 아래 수동 과정 대신 `main`에서 `workflow_dispatch`를
사용하는 것이 기본 배포 방법이다. 수동 ECR 업로드는 첫 배포 검증이나 CI/CD 장애 시에만 사용한다.

### 사전 조건

- 병합 충돌을 해결하고 필요한 변경을 commit한다.
- backend test/check와 Docker build를 로컬에서 먼저 통과시킨다.
- Docker Desktop이 Linux container mode로 실행 중이어야 한다.
- `aws sts get-caller-identity`의 account가 `511092105773`인지 확인한다.
- 운영용으로 이미 존재하는 immutable tag를 재사용하지 않는다.
- `.env`, 비밀번호, API key가 Docker build context나 image layer에 포함되지 않았는지 확인한다.

### PowerShell 세션 준비

새 PowerShell을 열 때마다 실행 파일과 profile 변수를 다시 선언한다.

```powershell
Set-Location C:\Users\Playdata\workspace\SKN28-final-2TEAM-main

$aws = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
$env:AWS_PROFILE = "skn28-terraform"
$env:AWS_REGION = "ap-northeast-2"

& $aws sts get-caller-identity
docker version
```

### 고유 image tag 생성

ECR repository가 immutable이므로 commit과 빌드 시각을 포함한 새 tag를 사용한다. `deploy-*` 형식을
사용하면 현재 ECR lifecycle의 최근 10개 보관 규칙에 포함된다.

```powershell
$accountId = (& $aws sts get-caller-identity --query Account --output text).Trim()
$registry = "$accountId.dkr.ecr.$env:AWS_REGION.amazonaws.com"
$repository = "tourmain/backend"
$commitSha = (git rev-parse HEAD).Trim()
$builtAt = Get-Date -Format "yyyyMMddHHmmss"
$imageTag = "deploy-$commitSha-manual-$builtAt"
$localImage = "tourmain-backend:$imageTag"
$remoteImage = "${registry}/${repository}:${imageTag}"

[PSCustomObject]@{
    Commit = $commitSha
    Tag = $imageTag
    RemoteImage = $remoteImage
}
```

build 전에 `git status --short`가 의도한 상태인지 확인한다. uncommitted 코드로 image를 만들면 tag의
commit과 실제 image 내용이 달라져 추적하기 어렵다.

### Backend image 빌드와 로컬 확인

현재 Fargate task와 맞도록 Linux AMD64 image를 만든다. build context는 저장소 root이고 Dockerfile은
`backend/Dockerfile`이다.

```powershell
docker build `
  --platform linux/amd64 `
  --file backend/Dockerfile `
  --tag $localImage `
  .

docker image inspect $localImage `
  --format '{{.Os}}/{{.Architecture}} {{.Id}}'

docker run --rm --entrypoint python $localImage --version
```

build가 성공해도 애플리케이션 test가 성공했다는 의미는 아니다. 앞 절의 Django test/check를 별도로
통과시켜야 한다.

### ECR 로그인과 업로드

```powershell
& $aws ecr describe-repositories `
  --repository-names $repository `
  --query "repositories[0].{Name:repositoryName,Uri:repositoryUri,Mutable:imageTagMutability,Scan:imageScanningConfiguration.scanOnPush}" `
  --output table

& $aws ecr get-login-password --region $env:AWS_REGION |
  docker login --username AWS --password-stdin $registry

docker tag $localImage $remoteImage
docker push $remoteImage
```

로그인 token이나 비밀번호를 변수로 출력하거나 문서에 복사하지 않는다.

### 업로드 결과 검증

```powershell
& $aws ecr describe-images `
  --repository-name $repository `
  --image-ids "imageTag=$imageTag" `
  --query "imageDetails[0].{Tags:imageTags,Digest:imageDigest,PushedAt:imagePushedAt,Size:imageSizeInBytes}" `
  --output table
```

`remoteImage`, ECR digest, commit SHA를 배포 기록에 남긴다. ECR push가 성공해도 실행 중인 ECS service는
아직 기존 task definition과 기존 image를 사용한다.

### ECR 업로드 이후 실제 Backend 배포

권장 경로는 GitHub Actions production workflow다. Workflow가 backend image build/push, 새 task
definition 등록, one-off migration/RDS/Chroma 검증, ECS service update, `/ready/` 검증과 rollback을
한 순서로 수행한다.

수동 업로드 image를 직접 배포해야 한다면 다음 순서를 지킨다.

1. 현재 ECS service의 task definition ARN을 기록한다.
2. 현재 task definition으로 새 revision을 만들고 backend container image만 `$remoteImage`로 교체한다.
3. 새 revision으로 one-off task를 실행해 Django migration, `verify_rds.py`, 증분 indexing,
   `verify_chroma.py`를 실행한다.
4. one-off task exit code가 `0`인지 CloudWatch log와 ECS에서 확인한다.
5. 성공한 revision으로 `tourmain-backend` service를 갱신하고 stable 상태를 기다린다.
6. ALB target, `/health/`, `/ready/`, CloudWatch alarm을 확인한다.
7. 실패하면 1번에서 기록한 이전 task definition으로 service를 rollback한다.

one-off migration을 생략하고 service부터 바꾸면 새 코드와 기존 DB schema가 충돌할 수 있다. ECR
업로드 성공만 보고 배포 완료로 판단하지 않는다.

### Frontend도 별도로 반영

Backend image는 React frontend 파일을 배포하지 않는다. 프론트 변경은 별도로 빌드하고 S3와
CloudFront에 반영한다.

```powershell
Set-Location frontend
npm ci
npm run build
Set-Location ..

& $aws s3 sync frontend/dist "s3://tourmain-frontend-511092105773" --delete
& $aws s3 cp frontend/dist/index.html `
  "s3://tourmain-frontend-511092105773/index.html" `
  --cache-control "no-cache,no-store,must-revalidate" `
  --content-type "text/html"

& $aws cloudfront create-invalidation `
  --distribution-id E19GBBQUW25GVT `
  --paths "/*"
```

## 11. 제거했으며 다시 만들지 않을 리소스

비용 절감을 위해 다음 기존 리소스를 삭제했다.

- legacy production EC2 instance
- EC2 root EBS 및 별도 Chroma EBS
- 기존 EBS snapshots
- DLM snapshot policy
- 기존 EC2 CloudWatch alarm
- 기존 EC2 instance role/profile
- planner SQS 및 DLQ
- DLQ alarm

현재 구조에서 필요성이 확인되기 전까지 다음을 추가하지 않는다.

- EC2 application server
- NAT Gateway
- WAF
- Route 53와 사용자 도메인
- ACM 사용자 인증서
- ECS Auto Scaling
- Container Insights
- SQS 비동기 planner

## 12. 남은 문제와 다음 작업

우선순위 순서:

1. 팀원의 최종 코드를 `main`에서 가져와 현재 배포 변경과 병합한다.
2. DB migration, 환경변수, health/readiness, Dockerfile, Terraform, workflow가 유실되지 않았는지 확인한다.
3. backend/frontend 테스트와 Docker build를 로컬에서 통과시킨다.
4. 새 코드 기준으로 Terraform `validate`와 새 `plan`을 확인한다.
5. Google OAuth의 승인된 JavaScript origin에 CloudFront URL을 등록한다.
6. Kakao Developers에 CloudFront 사이트 도메인과 redirect URI를 등록한다.
7. 로그인, 패키지 목록, 일정 생성, 저장, 조회 전체 흐름을 검증한다.
8. GitHub `production` environment를 확인하고 첫 수동 CI/CD 배포를 실행한다.
9. 배포 후 `/health/`, `/ready/`, CloudWatch alarm, ECS deployment 상태를 검증한다.

현재 알려진 사용자 기능 문제:

- Google 로그인: `400 origin_mismatch`
- Kakao 로그인: `KOE004`
- 로그인 실패 때문에 일정 생성 전체 흐름은 아직 검증하지 못했다.
- 패키지 목록이 표시되지 않는 현상은 로그인/OAuth 해결 후 API 응답과 DB 데이터를 함께 확인해야 한다.

## 13. 내일 병합 권장 절차

현재 변경을 잃지 않도록 먼저 `sim/merge-all`의 배포 변경을 commit으로 보존한다. 그다음 최신
`origin/main`을 가져와 현재 branch에 병합하고 충돌을 해결한다.

```powershell
git status --short
git diff --stat

# 현재 변경을 검토하고 필요한 파일만 stage/commit한 뒤 실행
git fetch origin
git merge origin/main
```

충돌 해결 기준:

- 팀원의 최신 도메인/화면/추천 로직은 반영한다.
- 이 문서의 DB, 운영 환경변수, health/readiness, Docker, Terraform, CI/CD 변경은 보존한다.
- migration 번호 충돌은 파일명을 임의로 덮어쓰지 말고 Django migration graph를 확인한다.
- `package-lock.json` 충돌은 수동 JSON 병합보다 최종 `package.json` 기준으로 `npm install` 후 재생성한다.
- 병합 직후 AWS에 push/apply하지 않고 먼저 로컬 테스트와 Terraform plan을 수행한다.

## 14. 안전한 검증 명령

PowerShell 세션 초기화:

```powershell
$aws = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
$terraform = "C:\Users\Playdata\Downloads\terraform_1.15.8_windows_amd64\terraform.exe"
$env:AWS_PROFILE = "skn28-terraform"
$env:AWS_REGION = "ap-northeast-2"
```

코드 검증:

```powershell
python backend/manage.py check
python backend/manage.py check --deploy --fail-level ERROR
python backend/manage.py migrate --database=default --check
python backend/manage.py test apps --noinput

Set-Location frontend
npm ci
npm run build
Set-Location ..

docker build --file backend/Dockerfile --tag tourmain-backend:local-check .
```

Terraform 읽기 전용 검증:

```powershell
Set-Location infra/terraform
& $terraform fmt -check
& $terraform validate
& $terraform plan -out="review.tfplan"
& $terraform show -no-color "review.tfplan"
```

AWS 읽기 전용 검증:

```powershell
& $aws sts get-caller-identity

& $aws ecs describe-services `
  --cluster tourmain-production `
  --services tourmain-backend tourmain-chroma

& $aws rds describe-db-instances `
  --db-instance-identifier tourmain-mysql

& $aws cloudwatch describe-alarms `
  --alarm-name-prefix tourmain
```

Secrets Manager에서는 key 이름과 ARN만 확인한다. `get-secret-value` 결과나 비밀번호를 터미널,
문서, 대화에 출력하지 않는다.

## 15. 새 Codex 작업 시작 프롬프트

새 작업은 이 저장소를 primary folder로 선택한 뒤 다음 프롬프트로 시작한다.

```text
먼저 docs/deployment/AWS_DEPLOYMENT_HANDOFF.md를 전부 읽어줘.

오늘 main에 병합된 코드와 기존 AWS 배포 변경을 비교해서 배포용 수정이 유실되거나 충돌한
부분을 찾아줘. 우선 읽기 전용으로 git status/log/diff, Terraform validate/plan, ECS/RDS/
CloudFront/S3 상태를 확인해줘.

DB migration, 운영 환경변수 검증, health/readiness, RDS bootstrap, Chroma HTTP/EFS 구성,
Terraform, GitHub Actions 변경은 유지해야 해. 먼저 변경 계획과 위험 요소를 보여주고,
terraform apply, Docker image push, ECS update, Git push는 내 확인 전에는 실행하지 마.
비밀값은 출력하지 마.
```

## 16. 완료 기준

다음 조건을 모두 만족하면 현재 운영 전환 작업이 완료된 것으로 본다.

- 최신 `main` 코드와 배포 변경 병합 완료
- backend test/check, frontend build, Docker build 성공
- Terraform plan에 예상하지 않은 destroy/replace 없음
- Google/Kakao 로그인 성공
- 패키지 목록과 일정 생성/저장/조회 성공
- GitHub Actions production 수동 배포 성공
- ECS backend/Chroma running `1/1`
- ALB target healthy
- `/ready/`에서 databases와 Chroma 모두 정상
- CloudWatch alarm 모두 정상 또는 원인이 설명된 상태
