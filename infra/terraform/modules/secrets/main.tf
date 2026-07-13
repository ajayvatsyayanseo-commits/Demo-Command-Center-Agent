variable "names" { type = set(string) }
variable "kms_key_arn" { type = string }
variable "recovery_window_days" { type = number }
variable "tags" { type = map(string) }

resource "aws_secretsmanager_secret" "this" {
  for_each                = var.names
  name                    = each.value
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_days
  tags                    = var.tags
}

output "secret_arns" { value = { for key, secret in aws_secretsmanager_secret.this : key => secret.arn } }
