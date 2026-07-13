variable "name" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "allowed_security_group_ids" { type = list(string) }
variable "node_type" { type = string }
variable "replicas" { type = number }
variable "kms_key_arn" { type = string }
variable "snapshot_retention_days" { type = number }
variable "automatic_failover_enabled" { type = bool }
variable "tags" { type = map(string) }

resource "aws_elasticache_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "this" {
  name_prefix = "${var.name}-redis-"
  description = "Redis TLS ingress from application tasks only"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "redis" {
  for_each                     = toset(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = each.value
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id       = var.name
  description                = "Demo Command Center cache, throttle, and lease state"
  node_type                  = var.node_type
  num_cache_clusters         = 1 + var.replicas
  engine                     = "redis"
  automatic_failover_enabled = var.automatic_failover_enabled && var.replicas > 0
  multi_az_enabled           = var.automatic_failover_enabled && var.replicas > 0
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  kms_key_id                 = var.kms_key_arn
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.this.id]
  snapshot_retention_limit   = var.snapshot_retention_days
  snapshot_window            = "17:00-18:00"
  maintenance_window         = "sun:18:30-sun:19:30"
  auto_minor_version_upgrade = true
  apply_immediately          = false
  tags                       = var.tags
}

output "primary_endpoint" { value = aws_elasticache_replication_group.this.primary_endpoint_address }
output "security_group_id" { value = aws_security_group.this.id }
output "replication_group_id" { value = aws_elasticache_replication_group.this.replication_group_id }
