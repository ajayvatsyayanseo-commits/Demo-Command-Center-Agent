# Terraform blueprint

Modules define the target AWS interfaces and safe defaults; they are not applied by this phase. Compose them per environment only after existing VPC/DNS/account discovery, capacity approval, provider quotas, SES status, backup/retention, and remote-state design are verified.

Never pass secret values where a Secrets Manager ARN/reference suffices. Use separate dev/staging/prod state and GitHub OIDC roles. Run `terraform fmt -check -recursive`, `terraform init -backend=false`, and `terraform validate`; apply only through protected environments.
