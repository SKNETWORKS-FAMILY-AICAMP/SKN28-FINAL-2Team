# Terraform adoption

이 디렉터리는 서울 리전의 기존 `tourmain` 운영 자원을 먼저 Terraform state로
가져오기 위한 최소 구성이다. 최초 adoption 단계에서는 AWS 자원을 새로 만들거나
수정하지 않는다.

## 범위

처음 가져오는 자원:

- `tourmain-vpc`, 6개 subnet, internet gateway
- ALB/application/RDS security group과 현재 규칙
- `tourmain-db-subnet-group`, `tourmain-mysql`
- 3개 ECR repository
- `tourmain/prod/mysql` secret의 메타데이터만 포함하고 secret value는 제외
- `/tourmain/prod/app` CloudWatch log group
- GitHub OIDC provider, 기존 GitHub deploy role과 inline policy

이번 단계에서 제외하는 자원:

- 삭제된 NAT를 가리키는 route table과 route association
- 기존 EC2, EBS, EC2 instance role
- 연결된 load balancer가 없는 target group
- default VPC와 `skn28-rds-dev-sg`
- RDS가 자동 생성한 CloudWatch log group

제외 자원은 adoption 완료 후 NAT/ECS/ALB/Chroma/S3/CloudFront 목표 구성을 만들 때
별도로 처리한다.

## 1. 로컬 인증

PowerShell 세션마다 다음 프로필을 선택한다. Access Key를 Terraform 파일이나
`tfvars`에 넣지 않는다.

```powershell
$env:AWS_PROFILE = "skn28-terraform"
$env:AWS_REGION = "ap-northeast-2"
```

## 2. state bucket bootstrap

현재 계정에는 S3 bucket이 없으므로 backend를 먼저 만든다. 아래 `apply`는 기존
운영 자원이 아니라 암호화·버전 관리·public 차단이 적용된 state bucket만 생성한다.

```powershell
Set-Location infra/terraform/bootstrap
terraform init
terraform plan "-out=bootstrap.tfplan"
terraform apply bootstrap.tfplan
```

## 3. 기존 자원 adoption plan

```powershell
Set-Location ..
Copy-Item backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl
terraform fmt -check
terraform validate
terraform plan "-out=adoption.tfplan"
terraform show -no-color adoption.tfplan
```

합격 조건은 **import만 존재하고 add/change/destroy가 모두 0**인 것이다. 하나라도
변경이 보이면 `terraform apply`를 실행하지 않고 `existing.tf`를 실제 AWS 상태와
맞춘다.

검토된 plan만 적용하면 선언적 `imports.tf`가 기존 자원을 state에 등록한다.

```powershell
terraform apply adoption.tfplan
terraform plan
```

두 번째 plan이 `No changes`여야 adoption이 완료된 것이다.

## 다음 단계

adoption 완료 후 별도 변경으로 다음을 추가한다.

1. blackhole route를 대체할 NAT gateway와 route table
2. ALB와 ECS Fargate backend
3. Chroma ECS, Cloud Map, EFS
4. frontend S3와 CloudFront
5. GitHub OIDC subject를 `production` environment에 맞추고 ECS/S3/CloudFront 권한 부여
6. ECR scan-on-push, VPC Flow Logs, 운영 경보

## 운영 고가용성 및 Blue/Green 전환

목표 구성은 다음과 같다.

- backend ECS 정상 상태: 두 태스크를 두 가용 영역에 분산
- backend 배포 상태: 기존 두 태스크와 신규 두 태스크를 함께 실행한 뒤 트래픽 전환
- RDS: 다른 가용 영역에 동기식 standby를 두는 Multi-AZ DB instance
- 배포 실패 감지: 두 target group의 unhealthy/5xx 경보와 ECS circuit breaker로 자동 rollback

기존 rolling 서비스를 Blue/Green으로 바꿀 때는 AWS 권고에 따라 한 번에 전환하지
않고 아래 두 단계로 적용한다. 각 단계 전에 `terraform show`에서 destroy가 0인지
확인한다.

### 1. RDS snapshot과 Rolling 기반 구성 준비

먼저 운영 RDS snapshot을 만든다. snapshot 생성 완료를 확인하기 전에는 Terraform을
적용하지 않는다.

```powershell
$snapshotId = "tourmain-mysql-before-multiaz-$(Get-Date -Format 'yyyyMMdd-HHmm')"
aws rds create-db-snapshot `
  --db-instance-identifier tourmain-mysql `
  --db-snapshot-identifier $snapshotId
aws rds wait db-snapshot-available --db-snapshot-identifier $snapshotId
```

첫 적용은 배포 전략을 Rolling으로 고정한다. 이 단계에서 backend 태스크 수 2,
RDS Multi-AZ, 보조 target group, listener rule, ECS load balancer 역할이 준비된다.

```powershell
terraform plan `
  -var='backend_deployment_strategy=ROLLING' `
  -out=ha-bootstrap.tfplan
terraform show -no-color ha-bootstrap.tfplan
terraform apply ha-bootstrap.tfplan
```

ECS가 `2/2` running이고 RDS가 `Available`, `Multi-AZ: Yes`인지 확인한다.

### 2. Blue/Green 활성화

```powershell
terraform plan `
  -var='backend_deployment_strategy=BLUE_GREEN' `
  -out=blue-green.tfplan
terraform show -no-color blue-green.tfplan
terraform apply blue-green.tfplan
```

이후 GitHub Actions의 production 수동 배포는 테스트 target group의 `/ready/`를 먼저
검증하고 production traffic을 전환한다. 전환 후 5분 동안 기존 revision을 유지하며,
CloudWatch 경보 또는 ECS circuit breaker가 실패를 감지하면 이전 revision으로
rollback한다.
