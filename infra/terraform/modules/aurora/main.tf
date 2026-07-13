variable "name" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" {
  type = list(string)
  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "Aurora requires data subnets in at least two availability zones."
  }
}
variable "allowed_security_group_ids" { type = list(string) }
variable "kms_key_arn" { type = string }
variable "engine_version" { type = string }
variable "capacity_mode" {
  description = "serverless_v2 or provisioned; choose using measured load and the documented cost decision."
  type        = string
  validation {
    condition     = contains(["serverless_v2", "provisioned"], var.capacity_mode)
    error_message = "capacity_mode must be serverless_v2 or provisioned."
  }
}
variable "instance_class" { type = string }
variable "instance_count" {
  type = number
  validation {
    condition     = var.instance_count >= 1
    error_message = "instance_count must be at least one."
  }
}
variable "min_acu" { type = number }
variable "max_acu" {
  type = number
  validation {
    condition     = var.max_acu >= var.min_acu
    error_message = "max_acu must be greater than or equal to min_acu."
  }
}
variable "backup_retention_days" {
  type = number
  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 1 and 35."
  }
}
variable "deletion_protection" { type = bool }
variable "performance_insights_enabled" { type = bool }
variable "performance_insights_retention_days" { type = number }
variable "tags" { type = map(string) }

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "this" {
  name_prefix = "${var.name}-db-"
  description = "Aurora PostgreSQL ingress from the RDS Proxy only"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  for_each                     = toset(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_rds_cluster" "this" {
  cluster_identifier              = var.name
  engine                          = "aurora-postgresql"
  engine_mode                     = "provisioned"
  engine_version                  = var.engine_version
  database_name                   = "demo_command_center"
  master_username                 = "demo_admin"
  manage_master_user_password     = true
  storage_encrypted               = true
  kms_key_id                      = var.kms_key_arn
  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = [aws_security_group.this.id]
  backup_retention_period         = var.backup_retention_days
  preferred_backup_window         = "18:00-19:00"
  preferred_maintenance_window    = "sun:19:30-sun:20:30"
  deletion_protection             = var.deletion_protection
  copy_tags_to_snapshot           = true
  enabled_cloudwatch_logs_exports = ["postgresql"]
  dynamic "serverlessv2_scaling_configuration" {
    for_each = var.capacity_mode == "serverless_v2" ? [1] : []
    content {
      min_capacity = var.min_acu
      max_capacity = var.max_acu
    }
  }
  tags = var.tags
}

resource "aws_rds_cluster_instance" "this" {
  count                                 = var.instance_count
  identifier                            = "${var.name}-${count.index + 1}"
  cluster_identifier                    = aws_rds_cluster.this.id
  instance_class                        = var.capacity_mode == "serverless_v2" ? "db.serverless" : var.instance_class
  engine                                = aws_rds_cluster.this.engine
  engine_version                        = aws_rds_cluster.this.engine_version
  auto_minor_version_upgrade            = true
  performance_insights_enabled          = var.performance_insights_enabled
  performance_insights_kms_key_id       = var.performance_insights_enabled ? var.kms_key_arn : null
  performance_insights_retention_period = var.performance_insights_enabled ? var.performance_insights_retention_days : null
  publicly_accessible                   = false
  tags                                  = var.tags
}

output "cluster_arn" { value = aws_rds_cluster.this.arn }
output "cluster_identifier" { value = aws_rds_cluster.this.cluster_identifier }
output "endpoint" { value = aws_rds_cluster.this.endpoint }
output "reader_endpoint" { value = aws_rds_cluster.this.reader_endpoint }
output "secret_arn" { value = aws_rds_cluster.this.master_user_secret[0].secret_arn }
output "security_group_id" { value = aws_security_group.this.id }
