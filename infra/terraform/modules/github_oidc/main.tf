variable "name_prefix" { type = string }
variable "github_organization" { type = string }
variable "github_repository" { type = string }
variable "roles" {
  description = "Separate least-privilege role policies and exact GitHub OIDC subject suffixes."
  type = map(object({
    policy_json      = string
    subject_suffixes = set(string)
  }))
  validation {
    condition     = alltrue([for role in values(var.roles) : length(role.subject_suffixes) > 0])
    error_message = "Every OIDC role requires at least one explicit subject suffix."
  }
}
variable "tags" { type = map(string) }

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
  tags            = var.tags
}

data "aws_iam_policy_document" "assume" {
  for_each = var.roles
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [for suffix in each.value.subject_suffixes : "repo:${var.github_organization}/${var.github_repository}:${suffix}"]
    }
  }
}

resource "aws_iam_role" "this" {
  for_each             = var.roles
  name                 = "${var.name_prefix}-${each.key}"
  assume_role_policy   = data.aws_iam_policy_document.assume[each.key].json
  max_session_duration = 3600
  tags                 = merge(var.tags, { CiRole = each.key })
}

resource "aws_iam_role_policy" "this" {
  for_each = var.roles
  name     = "${var.name_prefix}-${each.key}"
  role     = aws_iam_role.this[each.key].id
  policy   = each.value.policy_json
}

output "provider_arn" { value = aws_iam_openid_connect_provider.github.arn }
output "role_arns" { value = { for key, role in aws_iam_role.this : key => role.arn } }
