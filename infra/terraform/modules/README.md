# Module composition

Compose `network -> kms/secrets/iam -> aurora/rds_proxy/redis/sqs/s3 -> ecs/alb/waf/eventbridge/observability/glue_athena`. `dns_acm` is optional when an existing Route 53 zone/certificate is supplied. Interfaces avoid values specific to an AWS account.
