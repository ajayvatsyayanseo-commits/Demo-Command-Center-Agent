variable "name_prefix" { type = string }
variable "queue_names" { type = set(string) }
variable "kms_key_arn" { type = string }
variable "visibility_timeout_seconds" { type = number }
variable "message_retention_seconds" { type = number }
variable "max_receive_count" { type = number }
variable "tags" { type = map(string) }

resource "aws_sqs_queue" "dlq" {
  for_each                  = var.queue_names
  name                      = "${var.name_prefix}-${each.value}-dlq"
  kms_master_key_id         = var.kms_key_arn
  message_retention_seconds = var.message_retention_seconds
  tags                      = merge(var.tags, { QueueRole = "dead-letter" })
}

resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  for_each  = var.queue_names
  queue_url = aws_sqs_queue.dlq[each.key].id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.main[each.key].arn]
  })
}

resource "aws_sqs_queue" "main" {
  for_each                   = var.queue_names
  name                       = "${var.name_prefix}-${each.value}"
  kms_master_key_id          = var.kms_key_arn
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = 20
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = var.max_receive_count
  })
  tags = merge(var.tags, { QueueRole = "work" })
}

output "queue_urls" { value = { for key, queue in aws_sqs_queue.main : key => queue.url } }
output "queue_arns" { value = { for key, queue in aws_sqs_queue.main : key => queue.arn } }
output "queue_names" { value = { for key, queue in aws_sqs_queue.main : key => queue.name } }
output "dlq_arns" { value = { for key, queue in aws_sqs_queue.dlq : key => queue.arn } }
output "dlq_names" { value = { for key, queue in aws_sqs_queue.dlq : key => queue.name } }
