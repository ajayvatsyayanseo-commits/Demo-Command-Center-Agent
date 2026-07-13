# GitHub OIDC identity root

Apply this account-global root once, not once per environment. It creates one GitHub OIDC provider and five separately trusted roles: Terraform plan, dev deploy, staging deploy, production deploy, and rollback. Trust is restricted to this repository and exact GitHub Environment subjects.

`role_policies` is deliberately mandatory. Generate each JSON policy from the actual state bucket, ECR repository, ECS cluster/services, task roles, and environment resources; broad wildcard deployment policies are not accepted as an example. Review the rendered trust/policy plan with cloud security before apply. Store the resulting role ARNs as GitHub Environment variables named in `docs/operations/deployment.md`.

If the AWS account already has the GitHub OIDC provider, import it into this state or adapt the module through a reviewed change; never create a competing provider blindly.
