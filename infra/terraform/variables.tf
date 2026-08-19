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
  description = "Highly available backend ECS task count spread across two Availability Zones."
  type        = number
  default     = 2

  validation {
    condition     = var.backend_desired_count >= 2 && var.backend_desired_count <= 4
    error_message = "backend_desired_count must be between 2 and 4 for production high availability."
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
