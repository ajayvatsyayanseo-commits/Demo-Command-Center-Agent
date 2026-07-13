variable "bucket_names" { type = set(string) }
variable "kms_key_arn" { type = string }
variable "noncurrent_expiration_days" { type = number }
variable "alb_log_bucket_names" {
  type    = set(string)
  default = []
  validation {
    condition     = length(setsubtract(var.alb_log_bucket_names, var.bucket_names)) == 0
    error_message = "alb_log_bucket_names must be a subset of bucket_names."
  }
}
variable "tags" { type = map(string) }

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "this" {
  for_each = var.bucket_names
  bucket   = each.value
  tags     = var.tags
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each                = aws_s3_bucket.this
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_key_arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id
  rule {
    id     = "noncurrent-retention"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = var.noncurrent_expiration_days }
  }
}

data "aws_iam_policy_document" "this" {
  for_each = aws_s3_bucket.this
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      each.value.arn,
      "${each.value.arn}/*"
    ]
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
  dynamic "statement" {
    for_each = contains(var.alb_log_bucket_names, each.key) ? [1] : []
    content {
      sid       = "AllowAlbLogDelivery"
      effect    = "Allow"
      actions   = ["s3:PutObject"]
      resources = ["${each.value.arn}/alb/*/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]
      principals {
        type        = "Service"
        identifiers = ["logdelivery.elasticloadbalancing.amazonaws.com"]
      }
      condition {
        test     = "StringEquals"
        variable = "aws:SourceAccount"
        values   = [data.aws_caller_identity.current.account_id]
      }
    }
  }
  dynamic "statement" {
    for_each = contains(var.alb_log_bucket_names, each.key) ? [1] : []
    content {
      sid       = "AllowAlbAclCheck"
      effect    = "Allow"
      actions   = ["s3:GetBucketAcl"]
      resources = [each.value.arn]
      principals {
        type        = "Service"
        identifiers = ["logdelivery.elasticloadbalancing.amazonaws.com"]
      }
    }
  }
}

resource "aws_s3_bucket_policy" "this" {
  for_each   = aws_s3_bucket.this
  bucket     = each.value.id
  policy     = data.aws_iam_policy_document.this[each.key].json
  depends_on = [aws_s3_bucket_public_access_block.this]
}

output "bucket_arns" { value = { for key, bucket in aws_s3_bucket.this : key => bucket.arn } }
output "bucket_names" { value = { for key, bucket in aws_s3_bucket.this : key => bucket.bucket } }
