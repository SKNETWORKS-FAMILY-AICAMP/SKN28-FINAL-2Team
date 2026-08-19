locals {
  common_tags = {
    Environment = "prod"
    Project     = "tourmain"
    ManagedBy   = "terraform"
  }

  backend_image = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "tourmain/prod/app"
  description             = "Runtime secrets for the tourmain backend"
  recovery_window_in_days = 30

  tags = local.common_tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_security_group" "chroma" {
  name        = "tourmain-sg-chroma"
  description = "Private Chroma access from tourmain backend"
  vpc_id      = aws_vpc.production.id

  tags = merge(local.common_tags, { Name = "tourmain-sg-chroma" })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "chroma_from_app" {
  security_group_id            = aws_security_group.chroma.id
  referenced_security_group_id = aws_security_group.production["app"].id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  description                  = "Chroma API from backend tasks"
}

resource "aws_vpc_security_group_egress_rule" "chroma" {
  security_group_id = aws_security_group.chroma.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "efs" {
  name        = "tourmain-sg-efs"
  description = "NFS access for the tourmain Chroma service"
  vpc_id      = aws_vpc.production.id

  tags = merge(local.common_tags, { Name = "tourmain-sg-efs" })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "efs_from_chroma" {
  security_group_id            = aws_security_group.efs.id
  referenced_security_group_id = aws_security_group.chroma.id
  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
  description                  = "NFS from Chroma tasks"
}

resource "aws_vpc_security_group_egress_rule" "efs" {
  security_group_id = aws_security_group.efs.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_efs_file_system" "chroma" {
  creation_token   = "tourmain-prod-chroma"
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = merge(local.common_tags, { Name = "tourmain-prod-chroma" })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_efs_access_point" "chroma" {
  file_system_id = aws_efs_file_system.chroma.id

  posix_user {
    uid = 1000
    gid = 1000
  }

  root_directory {
    path = "/chroma"

    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0750"
    }
  }

  tags = local.common_tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_efs_mount_target" "chroma" {
  for_each = toset(["data_a", "data_b"])

  file_system_id  = aws_efs_file_system.chroma.id
  subnet_id       = aws_subnet.production[each.value].id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_backup_policy" "chroma" {
  file_system_id = aws_efs_file_system.chroma.id

  backup_policy {
    status = "ENABLED"
  }
}

resource "aws_cloudwatch_log_group" "chroma" {
  name              = "/tourmain/prod/chroma"
  retention_in_days = 14

  tags = local.common_tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role" "ecs_execution" {
  name = "tourmain-prod-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "tourmain-prod-ecs-secrets"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
      ]
      Resource = concat(
        [
          aws_secretsmanager_secret.mysql.arn,
          aws_secretsmanager_secret.app.arn,
        ],
        var.enable_rds_bootstrap ? [aws_db_instance.production.master_user_secret[0].secret_arn] : []
      )
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "tourmain-prod-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_ecs_cluster" "production" {
  name = "tourmain-production"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = local.common_tags
}

resource "aws_service_discovery_private_dns_namespace" "production" {
  name        = "tamrajeju.local"
  description = "Private service discovery for tourmain production"
  vpc         = aws_vpc.production.id

  tags = local.common_tags
}

resource "aws_service_discovery_service" "chroma" {
  name = "chroma"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.production.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  tags = local.common_tags
}

resource "aws_lb" "backend" {
  name                       = "tourmain-production-api"
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.production["alb"].id]
  subnets                    = [aws_subnet.production["public_a"].id, aws_subnet.production["public_b"].id]
  enable_deletion_protection = true
  idle_timeout               = 120

  tags = local.common_tags
}

resource "aws_lb_target_group" "backend" {
  name        = "tourmain-production-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.production.id

  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = "/health/"
    protocol            = "HTTP"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = local.common_tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_target_group" "backend_green" {
  name        = "tourmain-production-api-green"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.production.id

  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = "/health/"
    protocol            = "HTTP"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = local.common_tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_listener" "backend_http" {
  load_balancer_arn = aws_lb.backend.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

resource "aws_lb_listener_rule" "backend_production" {
  listener_arn = aws_lb_listener.backend_http.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/*"]
    }
  }

  # ECS swaps this rule between the blue and green target groups after each deployment.
  lifecycle {
    ignore_changes = [action]
  }
}

resource "aws_iam_role" "ecs_load_balancer" {
  name = "tourmain-prod-ecs-load-balancer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_load_balancer" {
  role       = aws_iam_role.ecs_load_balancer.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonECSInfrastructureRolePolicyForLoadBalancers"
}

resource "aws_ecs_task_definition" "chroma" {
  family                   = "tourmain-prod-chroma"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  volume {
    name = "chroma-data"

    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.chroma.id
      transit_encryption = "ENABLED"

      authorization_config {
        access_point_id = aws_efs_access_point.chroma.id
        iam             = "DISABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "chroma"
    image     = "chromadb/chroma:1.5.9"
    essential = true

    portMappings = [{
      name          = "chroma"
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]

    mountPoints = [{
      sourceVolume  = "chroma-data"
      containerPath = "/data"
      readOnly      = false
    }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.chroma.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "chroma"
      }
    }
  }])

  tags = local.common_tags
}

resource "aws_ecs_service" "chroma" {
  name            = "tourmain-chroma"
  cluster         = aws_ecs_cluster.production.id
  task_definition = aws_ecs_task_definition.chroma.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  network_configuration {
    subnets          = [aws_subnet.production["public_a"].id, aws_subnet.production["public_b"].id]
    security_groups  = [aws_security_group.chroma.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn = aws_service_discovery_service.chroma.arn
  }

  tags = local.common_tags

  depends_on = [
    aws_efs_mount_target.chroma,
    aws_iam_role_policy_attachment.ecs_execution,
  ]
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "tourmain-prod-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = local.backend_image
    essential = true

    portMappings = [{
      name          = "backend"
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "DJANGO_DEBUG", value = "false" },
      { name = "ALLOWED_HOSTS", value = "${aws_cloudfront_distribution.frontend.domain_name},${aws_lb.backend.dns_name}" },
      { name = "CORS_ALLOWED_ORIGINS", value = "https://${aws_cloudfront_distribution.frontend.domain_name}" },
      { name = "CSRF_TRUSTED_ORIGINS", value = "https://${aws_cloudfront_distribution.frontend.domain_name}" },
      { name = "SECURE_PROXY_SSL_HEADER_NAME", value = "HTTP_X_FORWARDED_SCHEME" },
      { name = "SECURE_SSL_REDIRECT", value = "true" },
      { name = "SESSION_COOKIE_SECURE", value = "true" },
      { name = "CSRF_COOKIE_SECURE", value = "true" },
      { name = "SECURE_HSTS_SECONDS", value = "0" },
      { name = "MYSQL_PORT", value = "3306" },
      { name = "ACCOUNT_DB_NAME", value = var.account_database_name },
      { name = "TRAVEL_DB_NAME", value = var.travel_database_name },
      { name = "MYSQL_DATABASE", value = var.travel_database_name },
      { name = "CHROMA_MODE", value = "http" },
      { name = "CHROMA_HOST", value = "chroma.tamrajeju.local" },
      { name = "CHROMA_PORT", value = "8000" },
      { name = "CHROMA_SSL", value = "false" },
      { name = "CHROMA_COLLECTION", value = "jeju_places" },
      { name = "OPENAI_EMBEDDING_MODEL", value = "text-embedding-3-small" },
      { name = "OPENAI_CHAT_MODEL", value = "gpt-4.1-mini" },
      { name = "KAKAO_REDIRECT_URI", value = "https://${aws_cloudfront_distribution.frontend.domain_name}/oauth/kakao/callback" },
    ]

    secrets = [
      { name = "DJANGO_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.app.arn}:DJANGO_SECRET_KEY::" },
      { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.app.arn}:OPENAI_API_KEY::" },
      { name = "GOOGLE_CLIENT_ID", valueFrom = "${aws_secretsmanager_secret.app.arn}:GOOGLE_CLIENT_ID::" },
      { name = "KAKAO_REST_API_KEY", valueFrom = "${aws_secretsmanager_secret.app.arn}:KAKAO_REST_API_KEY::" },
      { name = "KAKAO_CLIENT_SECRET", valueFrom = "${aws_secretsmanager_secret.app.arn}:KAKAO_CLIENT_SECRET::" },
      { name = "KAKAO_JAVASCRIPT_KEY", valueFrom = "${aws_secretsmanager_secret.app.arn}:KAKAO_JAVASCRIPT_KEY::" },
      { name = "MYSQL_HOST", valueFrom = "${aws_secretsmanager_secret.mysql.arn}:host::" },
      { name = "MYSQL_USER", valueFrom = "${aws_secretsmanager_secret.mysql.arn}:username::" },
      { name = "MYSQL_PASSWORD", valueFrom = "${aws_secretsmanager_secret.mysql.arn}:password::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "backend"
      }
    }
  }])

  tags = local.common_tags

  depends_on = [
    aws_iam_role_policy.ecs_execution_secrets,
    aws_iam_role_policy_attachment.ecs_execution,
  ]
}

resource "aws_ecs_task_definition" "rds_bootstrap" {
  count = var.enable_rds_bootstrap ? 1 : 0

  family                   = "tourmain-prod-rds-bootstrap"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "rds-bootstrap"
    image     = local.backend_image
    essential = true
    command   = ["python", "scripts/bootstrap_rds.py"]

    environment = [
      { name = "MYSQL_PORT", value = "3306" },
      { name = "ACCOUNT_DB_NAME", value = var.account_database_name },
      { name = "TRAVEL_DB_NAME", value = var.travel_database_name },
    ]

    secrets = [
      { name = "MYSQL_HOST", valueFrom = "${aws_secretsmanager_secret.mysql.arn}:host::" },
      { name = "MYSQL_USER", valueFrom = "${aws_secretsmanager_secret.mysql.arn}:username::" },
      { name = "MYSQL_PASSWORD", valueFrom = "${aws_secretsmanager_secret.mysql.arn}:password::" },
      { name = "MYSQL_ADMIN_USER", valueFrom = "${aws_db_instance.production.master_user_secret[0].secret_arn}:username::" },
      { name = "MYSQL_ADMIN_PASSWORD", valueFrom = "${aws_db_instance.production.master_user_secret[0].secret_arn}:password::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "rds-bootstrap"
      }
    }
  }])

  tags = local.common_tags

  depends_on = [
    aws_iam_role_policy.ecs_execution_secrets,
    aws_iam_role_policy_attachment.ecs_execution,
  ]
}

resource "aws_ecs_service" "backend" {
  name            = "tourmain-backend"
  cluster         = aws_ecs_cluster.production.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"

  availability_zone_rebalancing = "ENABLED"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 120

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_configuration {
    strategy             = "BLUE_GREEN"
    bake_time_in_minutes = 3
  }

  deployment_controller {
    type = "ECS"
  }

  alarms {
    alarm_names = [
      aws_cloudwatch_metric_alarm.alb_target_5xx.alarm_name,
      aws_cloudwatch_metric_alarm.alb_green_target_5xx.alarm_name,
    ]
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = [aws_subnet.production["public_a"].id, aws_subnet.production["public_b"].id]
    security_groups  = [aws_security_group.production["app"].id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000

    advanced_configuration {
      alternate_target_group_arn = aws_lb_target_group.backend_green.arn
      production_listener_rule   = aws_lb_listener_rule.backend_production.arn
      role_arn                   = aws_iam_role.ecs_load_balancer.arn
    }
  }

  tags = local.common_tags

  # GitHub Actions owns application task definition revisions.
  lifecycle {
    ignore_changes = [task_definition]
  }

  depends_on = [
    aws_iam_role_policy_attachment.ecs_load_balancer,
    aws_lb_listener_rule.backend_production,
  ]
}
