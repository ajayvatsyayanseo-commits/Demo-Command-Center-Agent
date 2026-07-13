variable "aws_region" { type = string }
variable "state_bucket_name" {
  description = "Globally unique state bucket name supplied by the account bootstrap owner."
  type        = string
}
variable "tags" {
  type = map(string)
  validation {
    condition     = alltrue([for key in ["Owner", "CostCenter", "DataClassification"] : contains(keys(var.tags), key)])
    error_message = "Bootstrap tags require Owner, CostCenter, and DataClassification."
  }
}

resource "aws_kms_key" "state" {
  description         = "Terraform state encryption"
  enable_key_rotation = true
  tags                = var.tags
  lifecycle { prevent_destroy = true }
}

resource "aws_kms_alias" "state" {
  name          = "alias/demo-command-center-terraform-state"
  target_key_id = aws_kms_key.state.key_id
}

resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name
  tags   = var.tags
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.state.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "old-noncurrent-state"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 365 }
  }
}

data "aws_iam_policy_document" "state" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state.json
}

output "state_bucket_name" { value = aws_s3_bucket.state.bucket }
output "state_kms_key_arn" { value = aws_kms_key.state.arn }
