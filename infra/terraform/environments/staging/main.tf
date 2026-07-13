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

variable "config" { type = any }

check "environment_matches_directory" {
  assert {
    condition     = var.config.environment == "staging"
    error_message = "The staging root accepts only config.environment = staging."
  }
}

provider "aws" {
  region = var.config.aws_region
  default_tags {
    tags = merge(var.config.tags, {
      Environment = "staging"
      Service     = "demo-command-center"
      ManagedBy   = "terraform"
    })
  }
}

module "environment" {
  source = "../_shared"
  config = var.config
}

output "platform" {
  value     = module.environment.platform
  sensitive = true
}
