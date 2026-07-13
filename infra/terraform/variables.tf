variable "aws_region" {
  description = "Deployment region supplied by the protected environment."
  type        = string
  validation {
    condition     = can(regex("^[a-z]{2}(-gov)?-[a-z]+-[0-9]$", var.aws_region))
    error_message = "aws_region must be a valid AWS region name."
  }
}

variable "environment" {
  description = "Isolated deployment environment."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "service_name" {
  type    = string
  default = "demo-command-center"
}

variable "tags" {
  description = "Cost, owner, data-classification, and environment-independent tags."
  type        = map(string)
  validation {
    condition     = alltrue([for key in ["Owner", "CostCenter", "DataClassification"] : contains(keys(var.tags), key) && trimspace(var.tags[key]) != ""])
    error_message = "tags must include non-empty Owner, CostCenter, and DataClassification values."
  }
}

variable "vpc_cidr" { type = string }
variable "availability_zones" { type = list(string) }
variable "nat_gateway_mode" {
  type = string
  validation {
    condition     = contains(["none", "single", "per_az"], var.nat_gateway_mode)
    error_message = "nat_gateway_mode must be none, single, or per_az."
  }
}
variable "interface_endpoint_services" {
  type    = set(string)
  default = ["ecr.api", "ecr.dkr", "logs", "secretsmanager", "sqs", "kms"]
}

variable "domain_name" {
  description = "Service FQDN in the approved Route 53 zone."
  type        = string
}
variable "hosted_zone_id" {
  description = "Existing Route 53 hosted zone ID; this stack does not transfer domain ownership."
  type        = string
}

variable "image_digest_uri" {
  description = "Release ECR image URI pinned to an immutable sha256 digest."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image_digest_uri))
    error_message = "image_digest_uri must end with @sha256 followed by 64 lowercase hexadecimal characters."
  }
}

variable "runtime_secrets" {
  description = "Map of task environment variable to empty Secrets Manager container name; values are populated out of band."
  type        = map(string)
  validation {
    condition     = length(var.runtime_secrets) > 0 && alltrue([for name in values(var.runtime_secrets) : !can(regex("(?i)(password=|token=|secret=|://[^/]+:[^@]+@)", name))])
    error_message = "runtime_secrets must contain secret names/references, never secret values."
  }
}

variable "container_environment" {
  description = "Additional non-secret runtime settings."
  type        = map(string)
  default     = {}
}

variable "bucket_names" {
  description = "Globally unique bucket names keyed by analytics, models, athena, and alb_logs."
  type        = map(string)
  validation {
    condition     = alltrue([for key in ["analytics", "models", "athena", "alb_logs"] : contains(keys(var.bucket_names), key)])
    error_message = "bucket_names requires analytics, models, athena, and alb_logs keys."
  }
}

variable "queue_names" {
  description = "Stable logical queue suffixes."
  type        = set(string)
  default = [
    "inbound",
    "scheduling",
    "outbound",
    "reminders",
    "payments",
    "analytics",
    "model-evaluation",
    "human-handoff"
  ]
}

variable "kms_deletion_window_days" { type = number }
variable "secret_recovery_window_days" { type = number }
variable "s3_noncurrent_expiration_days" { type = number }
variable "ecr_untagged_retention_days" { type = number }
variable "ecr_tagged_image_count" { type = number }

variable "aurora_engine_version" { type = string }
variable "aurora_capacity_mode" { type = string }
variable "aurora_instance_class" { type = string }
variable "aurora_instance_count" { type = number }
variable "aurora_min_acu" { type = number }
variable "aurora_max_acu" { type = number }
variable "backup_retention_days" { type = number }
variable "deletion_protection" { type = bool }
variable "performance_insights_enabled" { type = bool }
variable "performance_insights_retention_days" { type = number }
variable "rds_proxy_idle_timeout_seconds" { type = number }
variable "rds_proxy_max_connections_percent" { type = number }
variable "rds_proxy_max_idle_connections_percent" { type = number }

variable "redis_node_type" { type = string }
variable "redis_replicas" { type = number }
variable "redis_snapshot_retention_days" { type = number }
variable "redis_automatic_failover_enabled" { type = bool }

variable "sqs_visibility_timeout_seconds" { type = number }
variable "sqs_message_retention_seconds" { type = number }
variable "sqs_max_receive_count" { type = number }

variable "ecs_cpu" { type = number }
variable "ecs_memory" { type = number }
variable "api_desired_count" { type = number }
variable "worker_desired_count" { type = number }
variable "api_min_capacity" { type = number }
variable "api_max_capacity" { type = number }
variable "worker_min_capacity" { type = number }
variable "worker_max_capacity" { type = number }
variable "autoscaling_cpu_target" { type = number }
variable "worker_queue_depth_target" { type = number }
variable "worker_queue_age_threshold_seconds" { type = number }
variable "scale_in_cooldown_seconds" { type = number }
variable "scale_out_cooldown_seconds" { type = number }
variable "enable_execute_command" {
  type    = bool
  default = false
}

variable "waf_rate_limit" { type = number }
variable "log_retention_days" { type = number }
variable "queue_age_alarm_threshold_seconds" { type = number }
variable "queue_depth_alarm_threshold" { type = number }
variable "queue_alarm_evaluation_periods" { type = number }
variable "queue_alarm_period_seconds" { type = number }
variable "application_error_threshold" { type = number }
variable "signature_failure_threshold" { type = number }
variable "provider_failure_threshold" { type = number }
variable "payment_reconciliation_threshold" { type = number }

variable "athena_bytes_scanned_cutoff" { type = number }
variable "ses_sending_enabled" {
  description = "Enable only after the identity, production access, suppression, and complaint ownership are verified."
  type        = bool
  default     = false
}
variable "ses_identity_arns" {
  description = "Approved SES identity ARNs that task roles may use."
  type        = set(string)
  default     = []
}

variable "scheduled_jobs_enabled" {
  description = "Global gate for non-request scheduled jobs."
  type        = bool
  default     = false
}
variable "evaluation_schedule_expression" {
  type    = string
  default = "cron(0 2 * * ? *)"
}
variable "reconciliation_schedule_expression" {
  type    = string
  default = "rate(15 minutes)"
}
variable "retention_schedule_expression" {
  type    = string
  default = "cron(30 2 * * ? *)"
}
