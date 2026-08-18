# AWS CI/CD 설정

RDS를 처음 구성하거나 배포 직전 상태를 확인할 때는
[`rds_bootstrap.md`](rds_bootstrap.md)의 적재 순서와 자동 검증 명령을 먼저 실행한다.
Chroma/RAG는 [`chroma_production.md`](chroma_production.md)의 단일 private 서비스와
배포 전 증분 인덱싱 절차를 사용한다.

`.github/workflows/ci-cd.yml`은 pull request와 `main` push에서 CI를 실행한다.
실제 AWS 배포는 `main` 브랜치에서 `workflow_dispatch`로 수동 실행하고,
GitHub `production` environment를 사용한다.

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

관리자 권한이 있으면 **Settings → Environments → production**에 등록한다.
환경 설정 권한이 없으면 **Settings → Secrets and variables → Actions → Variables**의
repository variables에 같은 이름으로 등록해도 된다.

단일 운영환경에서는 변경 가능성이 있거나 외부 콘솔에서 발급되는 다음 5개만 등록한다.

| 이름 | 운영 값 |
| --- | --- |
| `AWS_ROLE_ARN` | `arn:aws:iam::511092105773:role/tourmain-github-deploy-role` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `E19GBBQUW25GVT` |
| `VITE_GOOGLE_CLIENT_ID` | 현재 운영 Google OAuth client ID |
| `VITE_KAKAO_JAVASCRIPT_KEY` | Kakao Maps용 JavaScript key |
| `VITE_KAKAO_LOGIN_JAVASCRIPT_KEY` | Kakao Login용 JavaScript key |

리전, ECR·ECS·S3 이름, CloudFront 도메인과 Kakao redirect URI는 현재 단일
운영환경의 고정값이므로 workflow에 명시한다. staging이나 별도 AWS 계정이 생길 때
environment variables로 분리한다.

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
