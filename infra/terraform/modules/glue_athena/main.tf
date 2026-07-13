variable "name" { type = string }
variable "analytics_bucket" { type = string }
variable "query_results_bucket" { type = string }
variable "kms_key_arn" { type = string }
variable "bytes_scanned_cutoff" { type = number }
variable "tags" { type = map(string) }

resource "aws_glue_catalog_database" "this" {
  name = replace(var.name, "-", "_")
}

resource "aws_athena_workgroup" "this" {
  name  = var.name
  state = "ENABLED"
  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.bytes_scanned_cutoff
    result_configuration {
      output_location = "s3://${var.query_results_bucket}/athena/"
      encryption_configuration {
        encryption_option = "SSE_KMS"
        kms_key_arn       = var.kms_key_arn
      }
    }
  }
  tags = var.tags
}

resource "aws_glue_catalog_table" "sanitized_events" {
  name          = "sanitized_demo_events_v1"
  database_name = aws_glue_catalog_database.this.name
  table_type    = "EXTERNAL_TABLE"
  parameters = {
    classification       = "parquet"
    EXTERNAL             = "TRUE"
    "projection.enabled" = "false"
  }
  storage_descriptor {
    location      = "s3://${var.analytics_bucket}/sanitized-events/v1/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
    columns {
      name = "schema_version"
      type = "string"
    }
    columns {
      name = "app_version"
      type = "string"
    }
    columns {
      name = "flow_version"
      type = "string"
    }
    columns {
      name = "policy_version"
      type = "string"
    }
    columns {
      name = "model_version"
      type = "string"
    }
    columns {
      name = "tenant_token"
      type = "string"
    }
    columns {
      name = "subject_token"
      type = "string"
    }
    columns {
      name = "region_id"
      type = "string"
    }
    columns {
      name = "occurred_at"
      type = "timestamp"
    }
    columns {
      name = "metric_name"
      type = "string"
    }
    columns {
      name = "metric_value"
      type = "double"
    }
  }
  partition_keys {
    name = "event_date"
    type = "date"
  }
  partition_keys {
    name = "event_type"
    type = "string"
  }
}

resource "aws_glue_catalog_table" "regional_metrics" {
  name          = "regional_metric_snapshots_v1"
  database_name = aws_glue_catalog_database.this.name
  table_type    = "EXTERNAL_TABLE"
  parameters    = { classification = "parquet", EXTERNAL = "TRUE" }
  storage_descriptor {
    location      = "s3://${var.analytics_bucket}/regional-metric-snapshots/v1/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
    columns {
      name = "tenant_token"
      type = "string"
    }
    columns {
      name = "region_id"
      type = "string"
    }
    columns {
      name = "window_start"
      type = "timestamp"
    }
    columns {
      name = "sample_size"
      type = "bigint"
    }
    columns {
      name = "metric_name"
      type = "string"
    }
    columns {
      name = "metric_value"
      type = "double"
    }
    columns {
      name = "baseline_value"
      type = "double"
    }
    columns {
      name = "practical_significance"
      type = "double"
    }
  }
  partition_keys {
    name = "snapshot_date"
    type = "date"
  }
}

resource "aws_athena_named_query" "regional_quality" {
  name        = "${var.name}-regional-quality"
  description = "Minimum-sample regional metric comparison; contains no direct identifiers."
  database    = aws_glue_catalog_database.this.name
  workgroup   = aws_athena_workgroup.this.id
  query       = file("${path.module}/queries/regional-quality.sql")
}

resource "aws_athena_named_query" "funnel" {
  name        = "${var.name}-demo-funnel"
  description = "Sanitized daily demo funnel by coarse region."
  database    = aws_glue_catalog_database.this.name
  workgroup   = aws_athena_workgroup.this.id
  query       = file("${path.module}/queries/demo-funnel.sql")
}

output "database_name" { value = aws_glue_catalog_database.this.name }
output "workgroup_name" { value = aws_athena_workgroup.this.name }
output "named_query_ids" { value = [aws_athena_named_query.regional_quality.id, aws_athena_named_query.funnel.id] }
