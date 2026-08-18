resource "aws_sns_topic" "alerts" {
  name = "tourmain-alerts"

  delivery_policy = jsonencode({
    http = {
      defaultHealthyRetryPolicy = {
        backoffFunction    = "linear"
        maxDelayTarget     = 20
        minDelayTarget     = 20
        numMaxDelayRetries = 0
        numMinDelayRetries = 0
        numNoDelayRetries  = 0
        numRetries         = 3
      }
      defaultRequestPolicy = {
        headerContentType = "text/plain; charset=UTF-8"
      }
      disableSubscriptionOverrides = false
    }
  })

  tags = {
    Project = "tourmain"
  }
}

# Preserve the existing low-storage alarm while bringing it under Terraform.
resource "aws_cloudwatch_metric_alarm" "rds_free_storage_low" {
  alarm_name                = "tourmain-mysql-free-storage-low"
  actions_enabled           = true
  alarm_actions             = [aws_sns_topic.alerts.arn]
  ok_actions                = []
  insufficient_data_actions = []

  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 4 * 1024 * 1024 * 1024
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "missing"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.production.identifier
  }
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_targets" {
  alarm_name                = "tourmain-alb-unhealthy-targets"
  alarm_description         = "Backend target is unhealthy for two consecutive minutes"
  alarm_actions             = [aws_sns_topic.alerts.arn]
  ok_actions                = []
  insufficient_data_actions = []

  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.backend.arn_suffix
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_targets_green" {
  alarm_name                = "tourmain-alb-unhealthy-targets-green"
  alarm_description         = "Alternate backend target is unhealthy for two consecutive minutes"
  alarm_actions             = [aws_sns_topic.alerts.arn]
  ok_actions                = []
  insufficient_data_actions = []

  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.backend.arn_suffix
    TargetGroup  = aws_lb_target_group.backend_green.arn_suffix
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_target_5xx" {
  alarm_name                = "tourmain-alb-target-5xx"
  alarm_description         = "Backend returned at least five 5xx responses in five minutes"
  alarm_actions             = [aws_sns_topic.alerts.arn]
  ok_actions                = []
  insufficient_data_actions = []

  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.backend.arn_suffix
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_target_5xx_green" {
  alarm_name                = "tourmain-alb-target-5xx-green"
  alarm_description         = "Alternate backend returned at least five 5xx responses in five minutes"
  alarm_actions             = [aws_sns_topic.alerts.arn]
  ok_actions                = []
  insufficient_data_actions = []

  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.backend.arn_suffix
    TargetGroup  = aws_lb_target_group.backend_green.arn_suffix
  }

  tags = local.common_tags
}

locals {
  ecs_alarm_services = {
    backend = aws_ecs_service.backend.name
    chroma  = aws_ecs_service.chroma.name
  }

  ecs_alarm_metrics = {
    cpu    = "CPUUtilization"
    memory = "MemoryUtilization"
  }

  ecs_alarms = {
    for pair in setproduct(keys(local.ecs_alarm_services), keys(local.ecs_alarm_metrics)) :
    "${pair[0]}_${pair[1]}" => {
      service_key = pair[0]
      metric_key  = pair[1]
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "ecs_utilization_high" {
  for_each = local.ecs_alarms

  alarm_name                = "tourmain-ecs-${each.value.service_key}-${each.value.metric_key}-high"
  alarm_description         = "${title(each.value.service_key)} ECS ${each.value.metric_key} utilization is at least 80% for ten minutes"
  alarm_actions             = [aws_sns_topic.alerts.arn]
  ok_actions                = []
  insufficient_data_actions = []

  namespace           = "AWS/ECS"
  metric_name         = local.ecs_alarm_metrics[each.value.metric_key]
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 80
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.production.name
    ServiceName = local.ecs_alarm_services[each.value.service_key]
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name                = "tourmain-rds-cpu-high"
  alarm_description         = "RDS CPU utilization is at least 80% for ten minutes"
  alarm_actions             = [aws_sns_topic.alerts.arn]
  ok_actions                = []
  insufficient_data_actions = []

  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 80
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.production.identifier
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_dashboard" "production" {
  dashboard_name = "tourmain-production"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ALB traffic and target health"
          region = var.aws_region
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.backend.arn_suffix, { label = "Requests" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", aws_lb.backend.arn_suffix, "TargetGroup", aws_lb_target_group.backend.arn_suffix, { label = "Blue target 5xx" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", aws_lb.backend.arn_suffix, "TargetGroup", aws_lb_target_group.backend_green.arn_suffix, { label = "Green target 5xx" }],
            ["AWS/ApplicationELB", "UnHealthyHostCount", "LoadBalancer", aws_lb.backend.arn_suffix, "TargetGroup", aws_lb_target_group.backend.arn_suffix, { label = "Blue unhealthy", stat = "Maximum", yAxis = "right" }],
            ["AWS/ApplicationELB", "UnHealthyHostCount", "LoadBalancer", aws_lb.backend.arn_suffix, "TargetGroup", aws_lb_target_group.backend_green.arn_suffix, { label = "Green unhealthy", stat = "Maximum", yAxis = "right" }],
          ]
          yAxis = {
            left  = { min = 0 }
            right = { min = 0 }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ECS service utilization"
          region = var.aws_region
          period = 300
          stat   = "Average"
          view   = "timeSeries"
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.production.name, "ServiceName", aws_ecs_service.backend.name, { label = "Backend CPU" }],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", aws_ecs_cluster.production.name, "ServiceName", aws_ecs_service.backend.name, { label = "Backend memory" }],
            ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.production.name, "ServiceName", aws_ecs_service.chroma.name, { label = "Chroma CPU" }],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", aws_ecs_cluster.production.name, "ServiceName", aws_ecs_service.chroma.name, { label = "Chroma memory" }],
          ]
          yAxis = {
            left = { min = 0, max = 100 }
          }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "RDS performance"
          region = var.aws_region
          period = 300
          stat   = "Average"
          view   = "timeSeries"
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.production.identifier, { label = "CPU (%)" }],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", aws_db_instance.production.identifier, { label = "Connections", yAxis = "right" }],
          ]
          yAxis = {
            left  = { min = 0, max = 100 }
            right = { min = 0 }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "RDS free storage"
          region = var.aws_region
          period = 300
          stat   = "Minimum"
          view   = "timeSeries"
          metrics = [
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", aws_db_instance.production.identifier, { label = "Free bytes" }],
          ]
          yAxis = {
            left = { min = 0 }
          }
        }
      },
    ]
  })
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "cloudwatch_dashboard_name" {
  value = aws_cloudwatch_dashboard.production.dashboard_name
}
