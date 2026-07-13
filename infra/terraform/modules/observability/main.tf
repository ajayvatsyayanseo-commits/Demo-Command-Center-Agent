variable "name" { type = string }
variable "metric_namespace" { type = string }
variable "kms_key_arn" { type = string }
variable "queue_names" { type = map(string) }
variable "dlq_names" { type = map(string) }
variable "queue_age_threshold_seconds" { type = number }
variable "queue_depth_threshold" { type = number }
variable "queue_alarm_evaluation_periods" { type = number }
variable "queue_alarm_period_seconds" { type = number }
variable "alb_arn_suffix" { type = string }
variable "target_group_arn_suffix" { type = string }
variable "ecs_cluster_name" { type = string }
variable "api_service_name" { type = string }
variable "worker_service_name" { type = string }
variable "db_cluster_identifier" { type = string }
variable "redis_replication_group_id" { type = string }
variable "application_error_threshold" { type = number }
variable "signature_failure_threshold" { type = number }
variable "provider_failure_threshold" { type = number }
variable "payment_reconciliation_threshold" { type = number }
variable "tags" { type = map(string) }

locals {
  alarm_actions = [aws_sns_topic.alarms.arn]
  custom_alarms = {
    signature-failures       = { metric = "SignatureFailures", threshold = var.signature_failure_threshold, dimensions = {} }
    duplicate-webhooks       = { metric = "DuplicateWebhookDetected", threshold = 10, dimensions = {} }
    meta-failures            = { metric = "ProviderFailures", threshold = var.provider_failure_threshold, dimensions = { Provider = "meta" } }
    google-calendar-failures = { metric = "ProviderFailures", threshold = var.provider_failure_threshold, dimensions = { Provider = "google_calendar" } }
    cashfree-failures        = { metric = "ProviderFailures", threshold = var.provider_failure_threshold, dimensions = { Provider = "cashfree" } }
    payment-reconciliation   = { metric = "PaymentReconciliationBacklog", threshold = var.payment_reconciliation_threshold, dimensions = {} }
    llm-fallback-spike       = { metric = "LlmFallbacks", threshold = 10, dimensions = {} }
    model-drift              = { metric = "ModelDriftBreaches", threshold = 0, dimensions = {} }
    conversion-anomaly       = { metric = "ConversionAnomalyBreaches", threshold = 0, dimensions = {} }
    no-show-anomaly          = { metric = "NoShowAnomalyBreaches", threshold = 0, dimensions = {} }
    pii-redaction-failure    = { metric = "PiiRedactionFailures", threshold = 0, dimensions = {} }
    duplicate-booking        = { metric = "DuplicateBookingAttempts", threshold = 0, dimensions = {} }
  }
  dashboards = {
    runtime = {
      title = "Runtime, API, and ECS"
      metrics = [
        ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix],
        ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix],
        ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.api_service_name],
        ["AWS/ECS", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.worker_service_name]
      ]
    }
    queues = {
      title = "Queues and DLQs"
      metrics = flatten([for queue in values(var.queue_names) : [
        ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", queue],
        ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", queue]
      ]])
    }
    providers = {
      title = "Providers, payments, and delivery"
      metrics = [
        [var.metric_namespace, "ProviderFailures", "Provider", "meta"],
        [var.metric_namespace, "ProviderFailures", "Provider", "google_calendar"],
        [var.metric_namespace, "ProviderFailures", "Provider", "cashfree"],
        [var.metric_namespace, "PaymentReconciliationBacklog"],
        [var.metric_namespace, "NotificationDelaySeconds"]
      ]
    }
    business = {
      title = "Demo funnel and regional performance"
      metrics = [
        [var.metric_namespace, "DemoStateTransitions", "State", "scheduled"],
        [var.metric_namespace, "DemoStateTransitions", "State", "completed"],
        [var.metric_namespace, "DemoStateTransitions", "State", "paid"],
        [var.metric_namespace, "NoShowRate"],
        [var.metric_namespace, "ConversionRate"]
      ]
    }
    security = {
      title = "Security and trust boundaries"
      metrics = [
        [var.metric_namespace, "SignatureFailures"],
        [var.metric_namespace, "ReplayRejected"],
        [var.metric_namespace, "RateLimitRejected"],
        [var.metric_namespace, "PiiRedactionFailures"]
      ]
    }
    model_cost = {
      title = "Model drift and LLM cost"
      metrics = [
        [var.metric_namespace, "LlmEstimatedCost"],
        [var.metric_namespace, "LlmFallbacks"],
        [var.metric_namespace, "ModelDriftScore"],
        [var.metric_namespace, "ForecastCalibrationError"]
      ]
    }
  }
}

resource "aws_sns_topic" "alarms" {
  name              = "${var.name}-alarms"
  kms_master_key_id = var.kms_key_arn
  tags              = var.tags
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_iam_policy_document" "alarm_topic" {
  statement {
    sid       = "AccountManagement"
    actions   = ["sns:GetTopicAttributes", "sns:SetTopicAttributes", "sns:Subscribe", "sns:Publish"]
    resources = [aws_sns_topic.alarms.arn]
    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
  statement {
    sid       = "ApprovedAwsPublishers"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alarms.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com", "ses.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "alarms" {
  arn    = aws_sns_topic.alarms.arn
  policy = data.aws_iam_policy_document.alarm_topic.json
}

resource "aws_cloudwatch_metric_alarm" "queue_age" {
  for_each            = var.queue_names
  alarm_name          = "${var.name}-${each.key}-oldest-message"
  alarm_description   = "High queue age; see docs/runbooks/sqs-backlog-and-dlq.md"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.queue_alarm_evaluation_periods
  datapoints_to_alarm = var.queue_alarm_evaluation_periods
  period              = var.queue_alarm_period_seconds
  statistic           = "Maximum"
  threshold           = var.queue_age_threshold_seconds
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = each.value }
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "queue_depth" {
  for_each            = var.queue_names
  alarm_name          = "${var.name}-${each.key}-backlog"
  alarm_description   = "Queue backlog exceeded the approved environment threshold."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.queue_alarm_evaluation_periods
  period              = var.queue_alarm_period_seconds
  statistic           = "Maximum"
  threshold           = var.queue_depth_threshold
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = each.value }
  alarm_actions       = local.alarm_actions
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "dlq" {
  for_each            = var.dlq_names
  alarm_name          = "${var.name}-${each.key}-dlq"
  alarm_description   = "Dead-letter queue contains messages; never bulk redrive without classification."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = each.value }
  alarm_actions       = local.alarm_actions
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name}-api-5xx"
  alarm_description   = "API target 5xx exceeded the release-safe threshold."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  period              = 60
  statistic           = "Sum"
  threshold           = var.application_error_threshold
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
  alarm_actions = local.alarm_actions
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "unhealthy_targets" {
  alarm_name          = "${var.name}-api-unhealthy-targets"
  alarm_description   = "ALB has unhealthy API targets; see deployment rollback runbook."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "breaching"
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
  alarm_actions = local.alarm_actions
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "aurora_cpu" {
  alarm_name          = "${var.name}-aurora-cpu"
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"
  dimensions          = { DBClusterIdentifier = var.db_cluster_identifier }
  alarm_actions       = local.alarm_actions
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  alarm_name          = "${var.name}-redis-memory"
  namespace           = "AWS/ElastiCache"
  metric_name         = "DatabaseMemoryUsagePercentage"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"
  dimensions          = { ReplicationGroupId = var.redis_replication_group_id }
  alarm_actions       = local.alarm_actions
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "custom" {
  for_each            = local.custom_alarms
  alarm_name          = "${var.name}-${each.key}"
  alarm_description   = "Application correctness/security alarm; use the mapped high-severity runbook."
  namespace           = var.metric_namespace
  metric_name         = each.value.metric
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  period              = 300
  statistic           = "Sum"
  threshold           = each.value.threshold
  treat_missing_data  = "notBreaching"
  dimensions          = each.value.dimensions
  alarm_actions       = local.alarm_actions
  tags                = var.tags
}

resource "aws_cloudwatch_dashboard" "this" {
  for_each       = local.dashboards
  dashboard_name = "${var.name}-${each.key}"
  dashboard_body = jsonencode({
    start          = "-PT6H"
    periodOverride = "inherit"
    widgets = [
      {
        type       = "text"
        x          = 0
        y          = 0
        width      = 24
        height     = 2
        properties = { markdown = "# ${each.value.title}\nNo raw PII or unbounded identifiers are permitted in metrics." }
      },
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 24
        height = 8
        properties = {
          title   = each.value.title
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          metrics = each.value.metrics
        }
      }
    ]
  })
}

data "aws_region" "current" {}

output "alarm_topic_arn" { value = aws_sns_topic.alarms.arn }
output "alarm_names" { value = concat(values(aws_cloudwatch_metric_alarm.custom)[*].alarm_name, values(aws_cloudwatch_metric_alarm.queue_age)[*].alarm_name, values(aws_cloudwatch_metric_alarm.dlq)[*].alarm_name) }
output "dashboard_names" { value = values(aws_cloudwatch_dashboard.this)[*].dashboard_name }
