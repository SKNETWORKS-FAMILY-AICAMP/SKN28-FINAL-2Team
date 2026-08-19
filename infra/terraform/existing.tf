locals {
  production_subnets = {
    public_a = {
      id   = "subnet-02438e1c21a146673"
      az   = "ap-northeast-2a"
      cidr = "10.20.0.0/20"
      name = "tourmain-subnet-public1-ap-northeast-2a"
    }
    public_b = {
      id   = "subnet-0ee43dfe8b42e35fd"
      az   = "ap-northeast-2b"
      cidr = "10.20.16.0/20"
      name = "tourmain-subnet-public2-ap-northeast-2b"
    }
    private_a = {
      id   = "subnet-0110af04dd55aff58"
      az   = "ap-northeast-2a"
      cidr = "10.20.128.0/20"
      name = "tourmain-subnet-private1-ap-northeast-2a"
    }
    private_b = {
      id   = "subnet-0ee1bde3ef6ecf5b4"
      az   = "ap-northeast-2b"
      cidr = "10.20.144.0/20"
      name = "tourmain-subnet-private2-ap-northeast-2b"
    }
    data_a = {
      id   = "subnet-00228066ade4ea3e5"
      az   = "ap-northeast-2a"
      cidr = "10.20.160.0/24"
      name = "tourmain-subnet-data1-ap-northeast-2a"
    }
    data_b = {
      id   = "subnet-05d4139c74d158503"
      az   = "ap-northeast-2b"
      cidr = "10.20.161.0/24"
      name = "tourmain-subnet-data2-ap-northeast-2b"
    }
  }

  security_groups = {
    alb = {
      id          = "sg-0fb78ac2d4b899f44"
      name        = "tourmain-sg-alb"
      description = "Internet-facing ALB for tourmain production"
    }
    app = {
      id          = "sg-068145f07b062d4c7"
      name        = "tourmain-sg-app"
      description = "Private EC2 application containers"
    }
    rds = {
      id          = "sg-0d1d73665c70a1010"
      name        = "tourmain-sg-rds"
      description = "Private MySQL access from application EC2"
    }
  }

  ingress_rules = {
    alb_http = {
      id                    = "sgr-0139442fc23e6e5d6"
      security_group        = "alb"
      from_port             = 80
      to_port               = 80
      cidr_ipv4             = null
      prefix_list_id        = data.aws_ec2_managed_prefix_list.cloudfront_origin_facing.id
      source_security_group = null
      description           = null
    }
    app_from_alb = {
      id                    = "sgr-01de0c4a49ec22275"
      security_group        = "app"
      from_port             = 8000
      to_port               = 8000
      cidr_ipv4             = null
      prefix_list_id        = null
      source_security_group = "alb"
      description           = "Allow ALB to backend"
    }
    rds_from_app = {
      id                    = "sgr-0ad1a95837bde1a4f"
      security_group        = "rds"
      from_port             = 3306
      to_port               = 3306
      cidr_ipv4             = null
      prefix_list_id        = null
      source_security_group = "app"
      description           = null
    }
  }

  egress_rule_ids = {
    alb = "sgr-08a0a9396bf529693"
    app = "sgr-0f8d7d9beda85030b"
    rds = "sgr-05fe4b8e922e91c8d"
  }

  backend_repository_name = "tourmain/backend"
}

data "aws_ec2_managed_prefix_list" "cloudfront_origin_facing" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_vpc" "production" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  instance_tenancy     = "default"

  tags = {
    Name = "tourmain-vpc"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_subnet" "production" {
  for_each = local.production_subnets

  vpc_id                  = aws_vpc.production.id
  availability_zone       = each.value.az
  cidr_block              = each.value.cidr
  map_public_ip_on_launch = false

  tags = {
    Name = each.value.name
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_internet_gateway" "production" {
  vpc_id = aws_vpc.production.id

  tags = {
    Name = "tourmain-igw"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_security_group" "production" {
  for_each = local.security_groups

  name        = each.value.name
  description = each.value.description
  vpc_id      = aws_vpc.production.id

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "production" {
  for_each = local.ingress_rules

  security_group_id            = aws_security_group.production[each.value.security_group].id
  ip_protocol                  = "tcp"
  from_port                    = each.value.from_port
  to_port                      = each.value.to_port
  cidr_ipv4                    = each.value.cidr_ipv4
  prefix_list_id               = each.value.prefix_list_id
  referenced_security_group_id = each.value.source_security_group == null ? null : aws_security_group.production[each.value.source_security_group].id
  description                  = each.value.description

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_egress_rule" "production" {
  for_each = local.egress_rule_ids

  security_group_id = aws_security_group.production[each.key].id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_db_subnet_group" "production" {
  name        = "tourmain-db-subnet-group"
  description = "Private data subnets for tourmain RDS"
  subnet_ids = [
    aws_subnet.production["data_a"].id,
    aws_subnet.production["data_b"].id,
  ]

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_db_instance" "production" {
  identifier = "tourmain-mysql"

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_type          = "gp3"
  iops                  = 3000
  storage_throughput    = 125
  storage_encrypted     = true
  kms_key_id            = "arn:aws:kms:ap-northeast-2:511092105773:key/7e9b58ad-a0b6-433d-a59e-36b14425445e"

  engine         = "mysql"
  engine_version = "8.4.9"
  instance_class = "db.t4g.micro"
  username       = "touradmin"
  port           = 3306

  db_subnet_group_name   = aws_db_subnet_group.production.name
  vpc_security_group_ids = [aws_security_group.production["rds"].id]
  publicly_accessible    = false
  multi_az               = true
  network_type           = "IPV4"

  parameter_group_name = "default.mysql8.4"
  option_group_name    = "default:mysql-8-4"

  backup_retention_period    = 14
  backup_window              = "13:21-13:51"
  maintenance_window         = "tue:19:42-tue:20:12"
  copy_tags_to_snapshot      = true
  deletion_protection        = true
  auto_minor_version_upgrade = true

  enabled_cloudwatch_logs_exports = ["error", "slowquery"]
  monitoring_interval             = 60
  monitoring_role_arn             = "arn:aws:iam::511092105773:role/rds-monitoring-role"
  performance_insights_enabled    = false
  ca_cert_identifier              = "rds-ca-rsa2048-g1"
  skip_final_snapshot             = true

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [apply_immediately, password]
  }
}

resource "aws_ecr_repository" "backend" {
  name                 = local.backend_repository_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "keep-latest-2-manual-images"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["manual-initial-*"]
          countType      = "imageCountMoreThan"
          countNumber    = 2
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "keep-latest-10-ci-images"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["deploy-*"]
          countType      = "imageCountMoreThan"
          countNumber    = 10
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 3
        description  = "delete-untagged-after-1-day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
    ]
  })
}

moved {
  from = aws_ecr_repository.production["backend"]
  to   = aws_ecr_repository.backend
}

removed {
  from = aws_ecr_repository.production

  lifecycle {
    destroy = true
  }
}

resource "aws_secretsmanager_secret" "mysql" {
  name = "tourmain/prod/mysql"

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      force_overwrite_replica_secret,
      recovery_window_in_days,
    ]
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/tourmain/prod/app"
  retention_in_days = 14

  tags = {
    Environment = "prod"
    Project     = "tourmain"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["ab9d0263244dd0326eb67015705a667e79cfe998"]

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = "tourmain-github-deploy-role"
  description          = "GitHub Actions deployment role for tourmain"
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = var.github_oidc_subject
        }
      }
    }]
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "tourmain-github-deploy-rolePolicy"
  role = aws_iam_role.github_deploy.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuthentication"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "PushTourmainImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
        ]
        Resource = aws_ecr_repository.backend.arn
      },
      {
        Sid    = "ReadECSDeploymentState"
        Effect = "Allow"
        Action = [
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:DescribeTasks",
        ]
        Resource = "*"
      },
      {
        Sid      = "RegisterBackendTaskDefinition"
        Effect   = "Allow"
        Action   = "ecs:RegisterTaskDefinition"
        Resource = "*"
      },
      {
        Sid      = "RunBackendDeploymentTasks"
        Effect   = "Allow"
        Action   = "ecs:RunTask"
        Resource = "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/tourmain-prod-backend:*"
        Condition = {
          ArnEquals = {
            "ecs:cluster" = aws_ecs_cluster.production.arn
          }
        }
      },
      {
        Sid      = "DeployBackendService"
        Effect   = "Allow"
        Action   = "ecs:UpdateService"
        Resource = aws_ecs_service.backend.id
      },
      {
        Sid      = "ReadRDSRecoveryPoint"
        Effect   = "Allow"
        Action   = "rds:DescribeDBInstances"
        Resource = "*"
      },
      {
        Sid    = "PassBackendTaskRoles"
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = [
          aws_iam_role.ecs_execution.arn,
          aws_iam_role.ecs_task.arn,
        ]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "ecs-tasks.amazonaws.com"
          }
        }
      },
      {
        Sid      = "PassECSLoadBalancerRole"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = aws_iam_role.ecs_load_balancer.arn
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "ecs.amazonaws.com"
          }
        }
      },
      {
        Sid    = "ReadFrontendBucket"
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:ListBucket",
        ]
        Resource = aws_s3_bucket.frontend.arn
      },
      {
        Sid    = "DeployFrontendObjects"
        Effect = "Allow"
        Action = [
          "s3:DeleteObject",
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = "${aws_s3_bucket.frontend.arn}/*"
      },
      {
        Sid      = "InvalidateFrontendCache"
        Effect   = "Allow"
        Action   = "cloudfront:CreateInvalidation"
        Resource = aws_cloudfront_distribution.frontend.arn
      },
    ]
  })

  lifecycle {
    prevent_destroy = true
  }
}

output "production_vpc_id" {
  value = aws_vpc.production.id
}

output "production_rds_identifier" {
  value = aws_db_instance.production.identifier
}
