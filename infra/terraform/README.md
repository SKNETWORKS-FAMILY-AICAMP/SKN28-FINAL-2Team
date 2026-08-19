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

## 운영 고가용성과 롤백

현재 목표 구성은 다음과 같다.

- backend ECS task 2개를 서울 리전의 두 Availability Zone에 분산
- 배포 중에만 기존 blue 2개와 신규 green 2개를 동시에 실행
- green의 `/ready/` 상태 검사 통과 후 운영 트래픽 전환
- 전환 후 10분 동안 기존 blue를 유지하고, task 기동 실패 또는 ALB 5xx 경보 시 자동 롤백
- RDS MySQL Multi-AZ standby와 7일 point-in-time recovery 사용
- 최근 CI 배포 이미지 10개 보존

Terraform 변경은 실제 운영 비용과 RDS 상태를 변경하므로 plan을 먼저 검토한다.

```powershell
$env:AWS_PROFILE = "skn28-terraform"
$env:AWS_REGION = "ap-northeast-2"
Set-Location infra/terraform
terraform init -backend-config=backend.hcl
terraform fmt -check
terraform validate
terraform plan "-out=ha.tfplan"
terraform show -no-color ha.tfplan
terraform apply ha.tfplan
```

RDS의 `multi_az = true` 변경은 기본적으로 다음 maintenance window에 적용된다.
즉시 적용하려고 AWS 콘솔에서 별도로 변경하면 일시적인 DB 연결 중단이 발생할 수 있다.

### 애플리케이션 수동 롤백

GitHub Actions의 **Roll back production backend** workflow를 실행하고 정상 동작했던
`tourmain-prod-backend:<revision>`을 입력한다. 롤백 역시 blue/green으로 실행되며,
대상 revision이 준비 상태 검사를 통과하지 못하면 시작 전 revision으로 복구한다.

### 데이터베이스 복구

배포 workflow는 migration 직전의 RDS `LatestRestorableTime`을 workflow summary에
기록한다. DB 복구는 기존 DB를 덮지 않고 새 인스턴스로 복원한 후 검증한다.

```powershell
aws rds restore-db-instance-to-point-in-time `
  --source-db-instance-identifier tourmain-mysql `
  --target-db-instance-identifier tourmain-mysql-restore-YYYYMMDDHHMM `
  --restore-time <workflow-summary의-UTC-시각> `
  --db-subnet-group-name tourmain-db-subnet-group `
  --no-publicly-accessible
```

복원 DB를 검증한 다음에만 `tourmain/prod/mysql` secret의 `host`를 새 endpoint로
변경하고 backend를 재배포한다. 자동으로 기존 DB를 덮어쓰지 않는 이유는 배포 이후
정상 입력된 운영 데이터까지 잃는 것을 막기 위해서다.
