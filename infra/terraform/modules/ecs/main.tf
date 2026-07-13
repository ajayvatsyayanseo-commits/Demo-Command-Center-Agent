variable "name" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "alb_security_group_id" { type = string }
variable "target_group_arn" { type = string }
variable "image_digest_uri" {
  type = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image_digest_uri))
    error_message = "image_digest_uri must be immutable and end with an sha256 digest."
  }
}
variable "execution_role_arn" { type = string }
variable "task_role_arn" { type = string }
variable "log_group_name" { type = string }
variable "container_environment" {
  description = "Non-secret task configuration only. Secret-like key names are rejected."
  type        = map(string)
  validation {
    condition = alltrue([
      for key in keys(var.container_environment) : length(regexall("(?i)(secret|password|token|api_key|private_key)", key)) == 0
    ])
    error_message = "container_environment cannot contain secret-like keys; use container_secret_arns."
  }
}
variable "container_secret_arns" {
  type      = map(string)
  sensitive = true
}
variable "api_desired_count" { type = number }
variable "worker_desired_count" { type = number }
variable "api_min_capacity" { type = number }
variable "api_max_capacity" { type = number }
variable "worker_min_capacity" { type = number }
variable "worker_max_capacity" { type = number }
variable "autoscaling_cpu_target" { type = number }
variable "worker_queue_name" { type = string }
variable "worker_queue_depth_target" { type = number }
variable "worker_queue_age_threshold_seconds" { type = number }
variable "scale_in_cooldown_seconds" { type = number }
variable "scale_out_cooldown_seconds" { type = number }
variable "cpu" { type = number }
variable "memory" { type = number }
variable "enable_execute_command" { type = bool }
variable "deployment_alarm_names" {
  description = "Pre-created CloudWatch alarms that trigger ECS deployment rollback."
  type        = list(string)
  default     = []
}
variable "tags" { type = map(string) }

data "aws_region" "current" {}

resource "aws_ecs_cluster" "this" {
  name = var.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  configuration {
    execute_command_configuration {
      logging = "DEFAULT"
    }
  }
  tags = var.tags
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    base              = 1
    weight            = 1
  }
}

resource "aws_security_group" "tasks" {
  name_prefix = "${var.name}-tasks-"
  description = "Application task traffic"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "api" {
  security_group_id            = aws_security_group.tasks.id
  referenced_security_group_id = var.alb_security_group_id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "tasks" {
  security_group_id = aws_security_group.tasks.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

locals {
  base_container = {
    image                  = var.image_digest_uri
    essential              = true
    user                   = "10001"
    readonlyRootFilesystem = true
    stopTimeout            = 30
    environment            = [for key, value in var.container_environment : { name = key, value = value }]
    secrets                = [for key, value in var.container_secret_arns : { name = key, valueFrom = value }]
    mountPoints            = [{ sourceVolume = "tmp", containerPath = "/tmp", readOnly = false }]
    linuxParameters = {
      initProcessEnabled = true
      capabilities       = { drop = ["ALL"] }
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = var.log_group_name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "app"
      }
    }
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  volume { name = "tmp" }
  container_definitions = jsonencode([
    merge(local.base_container, {
      name         = "api"
      command      = ["python", "-m", "uvicorn", "demo_command_center.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
      portMappings = [{ containerPort = 8080, protocol = "tcp", name = "http" }]
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=2)\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    })
  ])
  tags = var.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  volume { name = "tmp" }
  container_definitions = jsonencode([
    merge(local.base_container, {
      name    = "worker"
      command = ["python", "-m", "demo_command_center.workers"]
    })
  ])
  tags = var.tags
}

resource "aws_ecs_task_definition" "evaluation" {
  family                   = "${var.name}-evaluation"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  volume { name = "tmp" }
  container_definitions = jsonencode([
    merge(local.base_container, {
      name    = "evaluation"
      command = ["python", "-m", "demo_command_center.cli.evaluate_drift"]
    })
  ])
  tags = var.tags
}

resource "aws_ecs_service" "api" {
  name                               = "${var.name}-api"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.api_desired_count
  enable_execute_command             = var.enable_execute_command
  health_check_grace_period_seconds  = 60
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  propagate_tags                     = "SERVICE"
  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    base              = 1
    weight            = 1
  }
  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "api"
    container_port   = 8080
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  dynamic "alarms" {
    for_each = length(var.deployment_alarm_names) == 0 ? [] : [1]
    content {
      alarm_names = var.deployment_alarm_names
      enable      = true
      rollback    = true
    }
  }
  depends_on = [aws_ecs_cluster_capacity_providers.this]
  tags       = var.tags
}

resource "aws_ecs_service" "worker" {
  name                               = "${var.name}-worker"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.worker.arn
  desired_count                      = var.worker_desired_count
  enable_execute_command             = var.enable_execute_command
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  propagate_tags                     = "SERVICE"
  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    base              = 1
    weight            = 1
  }
  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = false
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  depends_on = [aws_ecs_cluster_capacity_providers.this]
  tags       = var.tags
}

resource "aws_appautoscaling_target" "worker" {
  max_capacity       = var.worker_max_capacity
  min_capacity       = var.worker_min_capacity
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "worker_queue_depth" {
  name               = "${var.name}-worker-queue-depth"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace
  target_tracking_scaling_policy_configuration {
    target_value       = var.worker_queue_depth_target
    scale_in_cooldown  = var.scale_in_cooldown_seconds
    scale_out_cooldown = var.scale_out_cooldown_seconds
    customized_metric_specification {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesVisible"
      statistic   = "Average"
      dimensions {
        name  = "QueueName"
        value = var.worker_queue_name
      }
    }
  }
}

resource "aws_appautoscaling_policy" "worker_age_scale_out" {
  name               = "${var.name}-worker-oldest-message"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace
  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = var.scale_out_cooldown_seconds
    metric_aggregation_type = "Maximum"
    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 2
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "worker_age_scale_out" {
  alarm_name          = "${var.name}-worker-scale-oldest-message"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  period              = 60
  statistic           = "Maximum"
  threshold           = var.worker_queue_age_threshold_seconds
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = var.worker_queue_name }
  alarm_actions       = [aws_appautoscaling_policy.worker_age_scale_out.arn]
  tags                = var.tags
}

resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.api_max_capacity
  min_capacity       = var.api_min_capacity
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace
  target_tracking_scaling_policy_configuration {
    target_value       = var.autoscaling_cpu_target
    scale_in_cooldown  = var.scale_in_cooldown_seconds
    scale_out_cooldown = var.scale_out_cooldown_seconds
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

output "cluster_name" { value = aws_ecs_cluster.this.name }
output "cluster_arn" { value = aws_ecs_cluster.this.arn }
output "api_service_name" { value = aws_ecs_service.api.name }
output "worker_service_name" { value = aws_ecs_service.worker.name }
output "api_task_definition_arn" { value = aws_ecs_task_definition.api.arn }
output "worker_task_definition_arn" { value = aws_ecs_task_definition.worker.arn }
output "evaluation_task_definition_arn" { value = aws_ecs_task_definition.evaluation.arn }
output "task_security_group_id" { value = aws_security_group.tasks.id }
