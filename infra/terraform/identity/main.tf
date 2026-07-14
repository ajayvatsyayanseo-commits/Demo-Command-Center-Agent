terraform {
  required_version = ">= 1.8.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}

variable "aws_region" { type = string }
variable "github_organization" { type = string }
variable "github_repository" { type = string }
variable "role_policies" {
  description = "Account-specific least-privilege JSON policies for each CI responsibility."
  type        = map(string)
  validation {
    condition = alltrue([
      for key in ["terraform-plan", "deploy-dev", "deploy-staging", "deploy-prod", "rollback"] : contains(keys(var.role_policies), key) && can(jsondecode(var.role_policies[key]))
    ])
    error_message = "Supply valid JSON for terraform-plan, deploy-dev, deploy-staging, deploy-prod, and rollback."
  }
}
variable "tags" { type = map(string) }

provider "aws" {
  region = var.aws_region
  default_tags { tags = var.tags }
}

locals {
  subjects = {
    terraform-plan = ["environment:dev", "environment:staging", "environment:prod"]
    deploy-dev     = ["environment:dev"]
    deploy-staging = ["environment:staging"]
    deploy-prod    = ["environment:production"]
    rollback       = ["environment:dev", "environment:staging", "environment:production"]
  }
  roles = {
    for name, policy in var.role_policies : name => {
      policy_json      = policy
      subject_suffixes = toset(local.subjects[name])
    }
  }
}

module "github_oidc" {
  source              = "../modules/github_oidc"
  name_prefix         = "demo-command-center"
  github_organization = var.github_organization
  github_repository   = var.github_repository
  roles               = local.roles
  tags                = var.tags
}

output "role_arns" { value = module.github_oidc.role_arns }
