variable "aws_region" {
  description = "AWS region that contains the production resources."
  type        = string
  default     = "ap-northeast-2"
}

variable "github_oidc_subject" {
  description = "GitHub OIDC subject restricted to the production environment."
  type        = string
  default     = "repo:SKNETWORKS-FAMILY-AICAMP@169222902/SKN28-FINAL-2Team@1309458796:environment:production"
}

variable "backend_image_tag" {
  description = "Immutable baseline image tag. GitHub Actions owns deployed task definition revisions."
  type        = string
  default     = "manual-initial-v8"
}

variable "enable_rds_bootstrap" {
  description = "Temporarily create the one-off RDS bootstrap task and grant access to the managed master secret."
  type        = bool
  default     = false
}

variable "backend_desired_count" {
  description = "Backend ECS task count. Production high availability requires at least two tasks."
  type        = number
  default     = 2

  validation {
    condition     = var.backend_desired_count >= 0 && var.backend_desired_count <= 4
    error_message = "backend_desired_count must be between 0 and 4."
  }
}

variable "backend_deployment_strategy" {
  description = "ECS deployment strategy. Use ROLLING for the first load balancer migration, then BLUE_GREEN."
  type        = string
  default     = "BLUE_GREEN"

  validation {
    condition     = contains(["ROLLING", "BLUE_GREEN"], upper(var.backend_deployment_strategy))
    error_message = "backend_deployment_strategy must be ROLLING or BLUE_GREEN."
  }
}

variable "backend_blue_green_bake_time_minutes" {
  description = "Minutes to keep both backend revisions after production traffic shifts."
  type        = number
  default     = 5

  validation {
    condition     = var.backend_blue_green_bake_time_minutes >= 1 && var.backend_blue_green_bake_time_minutes <= 30
    error_message = "backend_blue_green_bake_time_minutes must be between 1 and 30."
  }
}

variable "account_database_name" {
  description = "Django account database name."
  type        = string
  default     = "accounts_db"
}

variable "travel_database_name" {
  description = "Shared travel catalog database name."
  type        = string
  default     = "tour_recommender"
}
