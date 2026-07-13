variable "name" { type = string }
variable "vpc_subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }
variable "secret_arn" { type = string }
variable "kms_key_arn" { type = string }
variable "cluster_identifier" { type = string }
variable "idle_client_timeout" { type = number }
variable "max_connections_percent" { type = number }
variable "max_idle_connections_percent" { type = number }
variable "tags" { type = map(string) }

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "secret" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.secret_arn]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.name}-proxy"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "secret" {
  name   = "${var.name}-database-secret"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.secret.json
}

resource "aws_db_proxy" "this" {
  name                   = var.name
  debug_logging          = false
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = var.idle_client_timeout
  require_tls            = true
  role_arn               = aws_iam_role.this.arn
  vpc_security_group_ids = var.security_group_ids
  vpc_subnet_ids         = var.vpc_subnet_ids
  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = var.secret_arn
  }
  tags = var.tags
}

resource "aws_db_proxy_default_target_group" "this" {
  db_proxy_name = aws_db_proxy.this.name
  connection_pool_config {
    connection_borrow_timeout    = 30
    max_connections_percent      = var.max_connections_percent
    max_idle_connections_percent = var.max_idle_connections_percent
  }
}

resource "aws_db_proxy_target" "this" {
  db_cluster_identifier = var.cluster_identifier
  db_proxy_name         = aws_db_proxy.this.name
  target_group_name     = aws_db_proxy_default_target_group.this.name
}

output "endpoint" { value = aws_db_proxy.this.endpoint }
output "arn" { value = aws_db_proxy.this.arn }
output "role_arn" { value = aws_iam_role.this.arn }
