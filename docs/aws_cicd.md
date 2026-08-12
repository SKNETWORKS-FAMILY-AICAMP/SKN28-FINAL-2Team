# AWS CI/CD 설정

RDS를 처음 구성하거나 배포 직전 상태를 확인할 때는
[`rds_bootstrap.md`](rds_bootstrap.md)의 적재 순서와 자동 검증 명령을 먼저 실행한다.
Chroma/RAG는 [`chroma_production.md`](chroma_production.md)의 단일 private 서비스와
배포 전 증분 인덱싱 절차를 사용한다.

`.github/workflows/ci-cd.yml`은 pull request에서 CI를 실행하고, `main` 브랜치에
push되면 GitHub `production` environment를 통해 AWS에 배포한다.

## 배포 전 AWS 리소스

- ECR repository
- 기존 ECS Fargate service와 task definition
- private subnet에서 실행 가능한 ECS network configuration
- `chromadb/chroma:1.5.9` ECS service, Cloud Map private DNS, 암호화 EFS
- React 정적 파일을 저장할 S3 bucket
- S3를 origin으로 사용하는 CloudFront distribution
- GitHub OIDC provider를 신뢰하는 IAM role

ECS task definition에는 다음이 준비되어 있어야 한다.

- container name이 GitHub의 `ECS_CONTAINER_NAME`과 일치
- Secrets Manager를 통한 DB, Django, OpenAI, Google, Kakao 환경변수
- ALB health check 경로 `/health/`, 배포 smoke test 경로 `/ready/`
- RDS와 Chroma에 접근 가능한 security group
- OpenAI, Google, Kakao 호출을 위한 NAT 경로

## GitHub production environment variables

Repository의 **Settings → Environments → production**에 다음 variables를 등록한다.

| 이름 | 예시 |
| --- | --- |
| `AWS_REGION` | `ap-northeast-2` |
| `AWS_ROLE_ARN` | `arn:aws:iam::123456789012:role/github-actions-deploy` |
| `ECR_REPOSITORY` | `tamrajeju-backend` |
| `ECS_CLUSTER` | `tamrajeju-production` |
| `ECS_SERVICE` | `tamrajeju-api` |
| `ECS_CONTAINER_NAME` | `backend` |
| `FRONTEND_S3_BUCKET` | `tamrajeju-production-frontend` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `E1234567890` |
| `VITE_API_BASE_URL` | `https://api.example.com` |
| `VITE_GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `VITE_KAKAO_JAVASCRIPT_KEY` | Kakao JavaScript key |
| `VITE_KAKAO_REDIRECT_URI` | `https://example.com/oauth/kakao/callback` |

Vite variables는 브라우저에 포함되므로 비밀값을 넣지 않는다. `OPENAI_API_KEY`,
DB password, `DJANGO_SECRET_KEY`, Kakao client secret은 ECS task definition에서
Secrets Manager로 주입한다.

## OIDC IAM role 권한

배포 role은 해당 리소스로 범위를 제한한 다음 권한이 필요하다.

- ECR login 및 image push
- ECS service/task 조회, task definition 등록, migration task 실행, service 갱신
- ECS task role과 execution role에 대한 `iam:PassRole`
- frontend S3 bucket의 list, put, delete
- 대상 CloudFront distribution invalidation 생성

OIDC trust policy의 `sub` 조건은 production environment로 제한한다.

```json
{
  "StringEquals": {
    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
    "token.actions.githubusercontent.com:sub": "repo:OWNER/REPOSITORY:environment:production"
  }
}
```

## 배포 순서

1. Python/Django test와 check
2. React production build
3. backend Docker image build
4. commit SHA tag로 ECR push
5. 새 task definition 등록
6. 새 image로 migration, RDS 검증, Chroma 증분 인덱싱·검증 one-off task 실행
7. 모든 readiness 작업 성공 시 ECS service 갱신
8. frontend를 S3에 동기화하고 CloudFront invalidation 생성

GitHub `production` environment에 required reviewer를 설정하면 `main` push 후 실제
AWS 변경 전에 수동 승인을 받을 수 있다.

`main` branch protection에는 `backend`, `frontend`, `container` 세 job을 required
status checks로 등록한다. ECS service에는 deployment circuit breaker와 rollback을
활성화해 새 task가 health check를 통과하지 못하면 이전 revision으로 돌아가게 한다.
