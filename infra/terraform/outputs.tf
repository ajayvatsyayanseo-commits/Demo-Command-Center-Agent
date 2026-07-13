output "service_endpoint" { value = "https://${module.route53_alias.fqdn}" }
output "ecr_repository_url" { value = module.ecr.repository_url }
output "ecs_cluster_name" { value = module.ecs.cluster_name }
output "ecs_api_service_name" { value = module.ecs.api_service_name }
output "ecs_worker_service_name" { value = module.ecs.worker_service_name }
output "ecs_api_task_definition_arn" { value = module.ecs.api_task_definition_arn }
output "ecs_worker_task_definition_arn" { value = module.ecs.worker_task_definition_arn }
output "application_subnet_ids" { value = module.network.application_subnet_ids }
output "task_security_group_id" { value = module.ecs.task_security_group_id }
output "rds_proxy_endpoint" {
  value     = module.rds_proxy.endpoint
  sensitive = true
}
output "queue_urls" {
  value     = module.queues.queue_urls
  sensitive = true
}
output "runtime_secret_arns" {
  value     = module.secrets.secret_arns
  sensitive = true
}
output "alarm_topic_arn" { value = module.observability.alarm_topic_arn }
output "dashboard_names" { value = module.observability.dashboard_names }
output "schedule_group_name" { value = module.eventbridge.schedule_group_name }
output "athena_workgroup_name" { value = module.glue_athena.workgroup_name }
