variable "name" { type = string }
variable "sending_enabled" { type = bool }
variable "event_topic_arn" { type = string }
variable "tags" { type = map(string) }

resource "aws_sesv2_configuration_set" "this" {
  configuration_set_name = var.name
  sending_options { sending_enabled = var.sending_enabled }
  reputation_options { reputation_metrics_enabled = true }
  suppression_options { suppressed_reasons = ["BOUNCE", "COMPLAINT"] }
  tags = var.tags
}

resource "aws_sesv2_configuration_set_event_destination" "reputation" {
  configuration_set_name = aws_sesv2_configuration_set.this.configuration_set_name
  event_destination_name = "reputation-and-delivery"
  event_destination {
    enabled              = true
    matching_event_types = ["BOUNCE", "COMPLAINT", "REJECT", "DELIVERY_DELAY", "SUBSCRIPTION"]
    sns_destination { topic_arn = var.event_topic_arn }
  }
}

output "configuration_set_name" { value = aws_sesv2_configuration_set.this.configuration_set_name }
