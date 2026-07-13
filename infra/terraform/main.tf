data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  name             = "${var.service_name}-${var.environment}"
  metric_namespace = "NXTutors/DemoCommandCenter"
  common_tags = merge(var.tags, {
    Environment = var.environment
    Service     = var.service_name
    ManagedBy   = "terraform"
  })
  safe_container_environment = merge({
    APP_ENV                             = var.environment
    APP_NAME                            = "demo-command-center-agent"
    AWS_REGION                          = var.aws_region
    PROVIDER_PROFILE                    = "real"
    CLOUDWATCH_NAMESPACE                = local.metric_namespace
    META_DIRECT_WEBHOOK_ENABLED         = "false"
    META_OUTBOUND_ENABLED               = "false"
    META_OUTBOUND_PAUSED                = "true"
    DEMO_SCHEDULING_ENABLED             = "false"
    DEMO_REMINDERS_ENABLED              = "false"
    DEMO_PAYMENTS_ENABLED               = "false"
    DEMO_OUTBOUND_PAUSED                = "true"
    DEMO_NEW_BOOKINGS_PAUSED            = "true"
    DEMO_AUTOMATIC_DISCOUNT_ENABLED     = "false"
    DEMO_AUTOMATIC_PAYMENT_LINK_ENABLED = "false"
  }, var.container_environment)
  scheduler_role_arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${local.name}-scheduler"
  schedule_group_arn = "arn:${data.aws_partition.current.partition}:scheduler:${var.aws_region}:${data.aws_caller_identity.current.account_id}:schedule-group/${local.name}"
}

module "network" {
  source                      = "./modules/network"
  name                        = local.name
  vpc_cidr                    = var.vpc_cidr
  availability_zones          = var.availability_zones
  nat_gateway_mode            = var.nat_gateway_mode
  interface_endpoint_services = var.interface_endpoint_services
  tags                        = local.common_tags
}

module "kms" {
  source               = "./modules/kms"
  name                 = local.name
  deletion_window_days = var.kms_deletion_window_days
  tags                 = local.common_tags
}

module "storage" {
  source                     = "./modules/s3"
  bucket_names               = toset(values(var.bucket_names))
  alb_log_bucket_names       = toset([var.bucket_names["alb_logs"]])
  kms_key_arn                = module.kms.key_arn
  noncurrent_expiration_days = var.s3_noncurrent_expiration_days
  tags                       = local.common_tags
}

module "ecr" {
  source                  = "./modules/ecr"
  name                    = local.name
  kms_key_arn             = module.kms.key_arn
  untagged_retention_days = var.ecr_untagged_retention_days
  tagged_image_count      = var.ecr_tagged_image_count
  tags                    = local.common_tags
}

module "secrets" {
  source               = "./modules/secrets"
  names                = toset(values(var.runtime_secrets))
  kms_key_arn          = module.kms.key_arn
  recovery_window_days = var.secret_recovery_window_days
  tags                 = local.common_tags
}

module "queues" {
  source                     = "./modules/sqs"
  name_prefix                = local.name
  queue_names                = var.queue_names
  kms_key_arn                = module.kms.key_arn
  visibility_timeout_seconds = var.sqs_visibility_timeout_seconds
  message_retention_seconds  = var.sqs_message_retention_seconds
  max_receive_count          = var.sqs_max_receive_count
  tags                       = local.common_tags
}

resource "aws_security_group" "rds_proxy" {
  name_prefix = "${local.name}-proxy-"
  description = "RDS Proxy traffic between application tasks and Aurora"
  vpc_id      = module.network.vpc_id
  tags        = local.common_tags
}

module "aurora" {
  source                              = "./modules/aurora"
  name                                = local.name
  vpc_id                              = module.network.vpc_id
  subnet_ids                          = module.network.data_subnet_ids
  allowed_security_group_ids          = [aws_security_group.rds_proxy.id]
  kms_key_arn                         = module.kms.key_arn
  engine_version                      = var.aurora_engine_version
  capacity_mode                       = var.aurora_capacity_mode
  instance_class                      = var.aurora_instance_class
  instance_count                      = var.aurora_instance_count
  min_acu                             = var.aurora_min_acu
  max_acu                             = var.aurora_max_acu
  backup_retention_days               = var.backup_retention_days
  deletion_protection                 = var.deletion_protection
  performance_insights_enabled        = var.performance_insights_enabled
  performance_insights_retention_days = var.performance_insights_retention_days
  tags                                = local.common_tags
}

resource "aws_vpc_security_group_egress_rule" "rds_proxy_postgres" {
  security_group_id            = aws_security_group.rds_proxy.id
  referenced_security_group_id = module.aurora.security_group_id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

module "rds_proxy" {
  source                       = "./modules/rds_proxy"
  name                         = local.name
  vpc_subnet_ids               = module.network.data_subnet_ids
  security_group_ids           = [aws_security_group.rds_proxy.id]
  secret_arn                   = module.aurora.secret_arn
  kms_key_arn                  = module.kms.key_arn
  cluster_identifier           = module.aurora.cluster_identifier
  idle_client_timeout          = var.rds_proxy_idle_timeout_seconds
  max_connections_percent      = var.rds_proxy_max_connections_percent
  max_idle_connections_percent = var.rds_proxy_max_idle_connections_percent
  tags                         = local.common_tags
}

module "dns_acm" {
  source         = "./modules/dns_acm"
  domain_name    = var.domain_name
  hosted_zone_id = var.hosted_zone_id
  tags           = local.common_tags
}

module "alb" {
  source              = "./modules/alb"
  name                = local.name
  vpc_id              = module.network.vpc_id
  public_subnet_ids   = module.network.public_subnet_ids
  certificate_arn     = module.dns_acm.certificate_arn
  api_port            = 8080
  deletion_protection = var.deletion_protection
  access_logs_bucket  = module.storage.bucket_names[var.bucket_names["alb_logs"]]
  tags                = local.common_tags
  depends_on          = [module.storage]
}

module "waf" {
  source             = "./modules/waf"
  name               = local.name
  alb_arn            = module.alb.alb_arn
  rate_limit         = var.waf_rate_limit
  kms_key_arn        = module.kms.key_arn
  log_retention_days = var.log_retention_days
  tags               = local.common_tags
}

module "route53_alias" {
  source         = "./modules/route53_alias"
  domain_name    = var.domain_name
  hosted_zone_id = var.hosted_zone_id
  alb_dns_name   = module.alb.dns_name
  alb_zone_id    = module.alb.zone_id
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/ecs/${local.name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = module.kms.key_arn
  tags              = local.common_tags
}

data "aws_iam_policy_document" "task" {
  statement {
    sid = "Queues"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
      "sqs:SendMessage"
    ]
    resources = concat(values(module.queues.queue_arns), values(module.queues.dlq_arns))
  }
  statement {
    sid       = "StorageBuckets"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = values(module.storage.bucket_arns)
  }
  statement {
    sid       = "StorageObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload"]
    resources = [for arn in values(module.storage.bucket_arns) : "${arn}/*"]
  }
  statement {
    sid       = "RuntimeSecretReferences"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = values(module.secrets.secret_arns)
  }
  statement {
    sid       = "ApplicationEncryption"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = [module.kms.key_arn]
  }
  statement {
    sid = "SchedulerOperations"
    actions = [
      "scheduler:CreateSchedule",
      "scheduler:DeleteSchedule",
      "scheduler:GetSchedule",
      "scheduler:UpdateSchedule"
    ]
    resources = ["${local.schedule_group_arn}/*"]
  }
  statement {
    sid       = "PassSchedulerRole"
    actions   = ["iam:PassRole"]
    resources = [local.scheduler_role_arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["scheduler.amazonaws.com"]
    }
  }
  dynamic "statement" {
    for_each = length(var.ses_identity_arns) > 0 ? [1] : []
    content {
      sid       = "ApprovedEmailIdentities"
      actions   = ["ses:SendEmail", "ses:SendRawEmail"]
      resources = var.ses_identity_arns
    }
  }
  statement {
    sid       = "OperationalMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = [local.metric_namespace]
    }
  }
  statement {
    sid       = "DistributedTracing"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
}

module "iam" {
  source                = "./modules/iam"
  name                  = local.name
  task_policy_json      = data.aws_iam_policy_document.task.json
  execution_secret_arns = toset(values(module.secrets.secret_arns))
  kms_key_arn           = module.kms.key_arn
  tags                  = local.common_tags
}

module "ecs" {
  source                = "./modules/ecs"
  name                  = local.name
  vpc_id                = module.network.vpc_id
  subnet_ids            = module.network.application_subnet_ids
  alb_security_group_id = module.alb.security_group_id
  target_group_arn      = module.alb.target_group_arn
  image_digest_uri      = var.image_digest_uri
  execution_role_arn    = module.iam.execution_role_arn
  task_role_arn         = module.iam.task_role_arn
  log_group_name        = aws_cloudwatch_log_group.application.name
  container_environment = merge(local.safe_container_environment, {
    AWS_ACCOUNT_ID                 = data.aws_caller_identity.current.account_id
    SQS_INBOUND_QUEUE_URL          = module.queues.queue_urls["inbound"]
    SQS_SCHEDULING_QUEUE_URL       = module.queues.queue_urls["scheduling"]
    SQS_OUTBOUND_QUEUE_URL         = module.queues.queue_urls["outbound"]
    SQS_REMINDERS_QUEUE_URL        = module.queues.queue_urls["reminders"]
    SQS_PAYMENTS_QUEUE_URL         = module.queues.queue_urls["payments"]
    SQS_ANALYTICS_QUEUE_URL        = module.queues.queue_urls["analytics"]
    SQS_MODEL_EVALUATION_QUEUE_URL = module.queues.queue_urls["model-evaluation"]
    SQS_HUMAN_HANDOFF_QUEUE_URL    = module.queues.queue_urls["human-handoff"]
    S3_ANALYTICS_BUCKET            = module.storage.bucket_names[var.bucket_names["analytics"]]
    S3_MODEL_BUCKET                = module.storage.bucket_names[var.bucket_names["models"]]
    KMS_KEY_ARN                    = module.kms.key_arn
    EVENTBRIDGE_SCHEDULE_GROUP     = local.name
  })
  container_secret_arns              = { for env_name, secret_name in var.runtime_secrets : env_name => module.secrets.secret_arns[secret_name] }
  api_desired_count                  = var.api_desired_count
  worker_desired_count               = var.worker_desired_count
  api_min_capacity                   = var.api_min_capacity
  api_max_capacity                   = var.api_max_capacity
  worker_min_capacity                = var.worker_min_capacity
  worker_max_capacity                = var.worker_max_capacity
  autoscaling_cpu_target             = var.autoscaling_cpu_target
  worker_queue_name                  = module.queues.queue_names["inbound"]
  worker_queue_depth_target          = var.worker_queue_depth_target
  worker_queue_age_threshold_seconds = var.worker_queue_age_threshold_seconds
  scale_in_cooldown_seconds          = var.scale_in_cooldown_seconds
  scale_out_cooldown_seconds         = var.scale_out_cooldown_seconds
  cpu                                = var.ecs_cpu
  memory                             = var.ecs_memory
  enable_execute_command             = var.enable_execute_command
  deployment_alarm_names             = ["${local.name}-api-5xx", "${local.name}-api-unhealthy-targets"]
  tags                               = local.common_tags
}

resource "aws_vpc_security_group_ingress_rule" "rds_proxy_from_tasks" {
  security_group_id            = aws_security_group.rds_proxy.id
  referenced_security_group_id = module.ecs.task_security_group_id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

module "redis" {
  source                     = "./modules/redis"
  name                       = local.name
  vpc_id                     = module.network.vpc_id
  subnet_ids                 = module.network.data_subnet_ids
  allowed_security_group_ids = [module.ecs.task_security_group_id]
  node_type                  = var.redis_node_type
  replicas                   = var.redis_replicas
  kms_key_arn                = module.kms.key_arn
  snapshot_retention_days    = var.redis_snapshot_retention_days
  automatic_failover_enabled = var.redis_automatic_failover_enabled
  tags                       = local.common_tags
}

module "observability" {
  source                           = "./modules/observability"
  name                             = local.name
  metric_namespace                 = local.metric_namespace
  kms_key_arn                      = module.kms.key_arn
  queue_names                      = module.queues.queue_names
  dlq_names                        = module.queues.dlq_names
  queue_age_threshold_seconds      = var.queue_age_alarm_threshold_seconds
  queue_depth_threshold            = var.queue_depth_alarm_threshold
  queue_alarm_evaluation_periods   = var.queue_alarm_evaluation_periods
  queue_alarm_period_seconds       = var.queue_alarm_period_seconds
  alb_arn_suffix                   = module.alb.alb_arn_suffix
  target_group_arn_suffix          = module.alb.target_group_arn_suffix
  ecs_cluster_name                 = module.ecs.cluster_name
  api_service_name                 = module.ecs.api_service_name
  worker_service_name              = module.ecs.worker_service_name
  db_cluster_identifier            = module.aurora.cluster_identifier
  redis_replication_group_id       = module.redis.replication_group_id
  application_error_threshold      = var.application_error_threshold
  signature_failure_threshold      = var.signature_failure_threshold
  provider_failure_threshold       = var.provider_failure_threshold
  payment_reconciliation_threshold = var.payment_reconciliation_threshold
  tags                             = local.common_tags
}

module "ses" {
  source          = "./modules/ses"
  name            = local.name
  sending_enabled = var.ses_sending_enabled
  event_topic_arn = module.observability.alarm_topic_arn
  tags            = local.common_tags
}

module "eventbridge" {
  source             = "./modules/eventbridge"
  name               = local.name
  cluster_arn        = module.ecs.cluster_arn
  subnet_ids         = module.network.application_subnet_ids
  security_group_ids = [module.ecs.task_security_group_id]
  task_role_arn      = module.iam.task_role_arn
  execution_role_arn = module.iam.execution_role_arn
  schedules = {
    model-evaluation = {
      expression          = var.evaluation_schedule_expression
      timezone            = "UTC"
      task_definition_arn = module.ecs.evaluation_task_definition_arn
      container_name      = "evaluation"
      command             = ["python", "-m", "demo_command_center.cli.evaluate_drift"]
      use_fargate_spot    = true
      enabled             = var.scheduled_jobs_enabled
    }
    payment-reconciliation = {
      expression          = var.reconciliation_schedule_expression
      timezone            = "UTC"
      task_definition_arn = module.ecs.worker_task_definition_arn
      container_name      = "worker"
      command             = ["python", "-m", "demo_command_center.cli.reconcile_payments"]
      use_fargate_spot    = false
      enabled             = var.scheduled_jobs_enabled
    }
    retention-cleanup = {
      expression          = var.retention_schedule_expression
      timezone            = "UTC"
      task_definition_arn = module.ecs.worker_task_definition_arn
      container_name      = "worker"
      command             = ["python", "-m", "demo_command_center.cli.retention_cleanup"]
      use_fargate_spot    = false
      enabled             = var.scheduled_jobs_enabled
    }
  }
  tags = local.common_tags
}

module "glue_athena" {
  source               = "./modules/glue_athena"
  name                 = local.name
  analytics_bucket     = module.storage.bucket_names[var.bucket_names["analytics"]]
  query_results_bucket = module.storage.bucket_names[var.bucket_names["athena"]]
  kms_key_arn          = module.kms.key_arn
  bytes_scanned_cutoff = var.athena_bytes_scanned_cutoff
  tags                 = local.common_tags
}
