variable "name" { type = string }
variable "cluster_arn" { type = string }
variable "subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }
variable "task_role_arn" { type = string }
variable "execution_role_arn" { type = string }
variable "schedules" {
  type = map(object({
    expression          = string
    timezone            = string
    task_definition_arn = string
    container_name      = string
    command             = list(string)
    use_fargate_spot    = bool
    enabled             = bool
  }))
}
variable "tags" { type = map(string) }

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["ecs:RunTask"]
    resources = distinct([for schedule in values(var.schedules) : schedule.task_definition_arn])
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [var.cluster_arn]
    }
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = [var.task_role_arn, var.execution_role_arn]
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "${var.name}-run-approved-tasks"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule_group" "this" {
  name = var.name
  tags = var.tags
}

resource "aws_scheduler_schedule" "this" {
  for_each                     = var.schedules
  name                         = "${var.name}-${each.key}"
  group_name                   = aws_scheduler_schedule_group.this.name
  schedule_expression          = each.value.expression
  schedule_expression_timezone = each.value.timezone
  state                        = each.value.enabled ? "ENABLED" : "DISABLED"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = var.cluster_arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      containerOverrides = [{
        name    = each.value.container_name
        command = each.value.command
      }]
    })
    ecs_parameters {
      task_definition_arn    = each.value.task_definition_arn
      task_count             = 1
      launch_type            = each.value.use_fargate_spot ? null : "FARGATE"
      platform_version       = "LATEST"
      enable_execute_command = false
      dynamic "capacity_provider_strategy" {
        for_each = each.value.use_fargate_spot ? [1] : []
        content {
          capacity_provider = "FARGATE_SPOT"
          weight            = 1
        }
      }
      network_configuration {
        assign_public_ip = false
        security_groups  = var.security_group_ids
        subnets          = var.subnet_ids
      }
    }
  }
}

output "schedule_group_name" { value = aws_scheduler_schedule_group.this.name }
output "scheduler_role_arn" { value = aws_iam_role.scheduler.arn }
output "schedule_arns" { value = { for key, schedule in aws_scheduler_schedule.this : key => schedule.arn } }
