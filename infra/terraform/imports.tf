import {
  to = aws_vpc.production
  id = "vpc-0ee34cc6074d7f2c2"
}

import {
  for_each = local.production_subnets
  to       = aws_subnet.production[each.key]
  id       = each.value.id
}

import {
  to = aws_internet_gateway.production
  id = "igw-0ac86a685cd049653"
}

import {
  for_each = local.security_groups
  to       = aws_security_group.production[each.key]
  id       = each.value.id
}

import {
  for_each = local.ingress_rules
  to       = aws_vpc_security_group_ingress_rule.production[each.key]
  id       = each.value.id
}

import {
  for_each = local.egress_rule_ids
  to       = aws_vpc_security_group_egress_rule.production[each.key]
  id       = each.value
}

import {
  to = aws_db_subnet_group.production
  id = "tourmain-db-subnet-group"
}

import {
  to = aws_db_instance.production
  id = "tourmain-mysql"
}

import {
  to = aws_ecr_lifecycle_policy.backend
  id = "tourmain/backend"
}

import {
  to = aws_secretsmanager_secret.mysql
  id = "arn:aws:secretsmanager:ap-northeast-2:511092105773:secret:tourmain/prod/mysql-q9LfQT"
}

import {
  to = aws_cloudwatch_log_group.app
  id = "/tourmain/prod/app"
}

import {
  to = aws_sns_topic.alerts
  id = "arn:aws:sns:ap-northeast-2:511092105773:tourmain-alerts"
}

import {
  to = aws_cloudwatch_metric_alarm.rds_free_storage_low
  id = "tourmain-mysql-free-storage-low"
}

import {
  to = aws_iam_openid_connect_provider.github
  id = "arn:aws:iam::511092105773:oidc-provider/token.actions.githubusercontent.com"
}

import {
  to = aws_iam_role.github_deploy
  id = "tourmain-github-deploy-role"
}

import {
  to = aws_iam_role_policy.github_deploy
  id = "tourmain-github-deploy-role:tourmain-github-deploy-rolePolicy"
}
