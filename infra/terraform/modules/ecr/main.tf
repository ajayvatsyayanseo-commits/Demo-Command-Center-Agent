variable "name" { type = string }
variable "kms_key_arn" { type = string }
variable "untagged_retention_days" { type = number }
variable "tagged_image_count" { type = number }
variable "tags" { type = map(string) }

resource "aws_ecr_repository" "this" {
  name                 = var.name
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = var.kms_key_arn
  }
  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name
  policy = jsonencode({ rules = [
    {
      rulePriority = 1
      description  = "Expire untagged images"
      selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = var.untagged_retention_days }
      action       = { type = "expire" }
    },
    {
      rulePriority = 2
      description  = "Bound immutable release image retention"
      selection    = { tagStatus = "tagged", tagPrefixList = ["sha-"], countType = "imageCountMoreThan", countNumber = var.tagged_image_count }
      action       = { type = "expire" }
    }
  ] })
}

output "repository_url" { value = aws_ecr_repository.this.repository_url }
output "repository_name" { value = aws_ecr_repository.this.name }
