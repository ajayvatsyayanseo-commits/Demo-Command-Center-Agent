variable "name" { type = string }
variable "vpc_cidr" {
  type = string
  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR."
  }
}
variable "availability_zones" {
  type = list(string)
  validation {
    condition     = length(var.availability_zones) >= 2 && length(var.availability_zones) <= 4 && length(distinct(var.availability_zones)) == length(var.availability_zones)
    error_message = "Supply two to four distinct availability zones."
  }
}
variable "nat_gateway_mode" {
  description = "none for isolated test environments, single for lower-cost non-production, or per_az for resilient production egress."
  type        = string
  validation {
    condition     = contains(["none", "single", "per_az"], var.nat_gateway_mode)
    error_message = "nat_gateway_mode must be none, single, or per_az."
  }
}
variable "interface_endpoint_services" {
  description = "AWS service suffixes (for example ecr.api) approved after NAT-versus-endpoint cost review."
  type        = set(string)
  default     = []
}
variable "tags" { type = map(string) }

locals {
  az_map               = { for index, az in var.availability_zones : az => index }
  first_az             = var.availability_zones[0]
  nat_azs              = var.nat_gateway_mode == "per_az" ? toset(var.availability_zones) : var.nat_gateway_mode == "single" ? toset([local.first_az]) : toset([])
  app_route_table_ids  = [for route_table in aws_route_table.application : route_table.id]
  data_route_table_ids = [for route_table in aws_route_table.data : route_table.id]
}

data "aws_region" "current" {}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = var.name })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-igw" })
}

resource "aws_subnet" "public" {
  for_each                = local.az_map
  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, each.value)
  map_public_ip_on_launch = false
  tags                    = merge(var.tags, { Tier = "public", Name = "${var.name}-public-${each.key}" })
}

resource "aws_subnet" "application" {
  for_each          = local.az_map
  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, 4 + each.value)
  tags              = merge(var.tags, { Tier = "application", Name = "${var.name}-app-${each.key}" })
}

resource "aws_subnet" "data" {
  for_each          = local.az_map
  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, 8 + each.value)
  tags              = merge(var.tags, { Tier = "data", Name = "${var.name}-data-${each.key}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(var.tags, { Name = "${var.name}-public" })
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  for_each   = local.nat_azs
  domain     = "vpc"
  tags       = merge(var.tags, { Name = "${var.name}-nat-${each.key}" })
  depends_on = [aws_internet_gateway.this]
}

resource "aws_nat_gateway" "this" {
  for_each      = local.nat_azs
  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id
  tags          = merge(var.tags, { Name = "${var.name}-nat-${each.key}" })
  depends_on    = [aws_route_table_association.public]
}

resource "aws_route_table" "application" {
  for_each = local.az_map
  vpc_id   = aws_vpc.this.id
  tags     = merge(var.tags, { Name = "${var.name}-app-${each.key}" })
}

resource "aws_route" "application_egress" {
  for_each               = var.nat_gateway_mode == "none" ? {} : local.az_map
  route_table_id         = aws_route_table.application[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[var.nat_gateway_mode == "single" ? local.first_az : each.key].id
}

resource "aws_route_table_association" "application" {
  for_each       = aws_subnet.application
  subnet_id      = each.value.id
  route_table_id = aws_route_table.application[each.key].id
}

resource "aws_route_table" "data" {
  for_each = local.az_map
  vpc_id   = aws_vpc.this.id
  tags     = merge(var.tags, { Name = "${var.name}-data-${each.key}" })
}

resource "aws_route_table_association" "data" {
  for_each       = aws_subnet.data
  subnet_id      = each.value.id
  route_table_id = aws_route_table.data[each.key].id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(local.app_route_table_ids, local.data_route_table_ids)
  tags              = merge(var.tags, { Name = "${var.name}-s3" })
}

resource "aws_security_group" "endpoints" {
  name_prefix = "${var.name}-endpoints-"
  description = "TLS access to explicitly enabled AWS interface endpoints"
  vpc_id      = aws_vpc.this.id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_https" {
  security_group_id = aws_security_group.endpoints.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = var.interface_endpoint_services
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.${each.key}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = values(aws_subnet.application)[*].id
  security_group_ids  = [aws_security_group.endpoints.id]
  tags                = merge(var.tags, { Name = "${var.name}-${replace(each.key, ".", "-")}" })
}

output "vpc_id" { value = aws_vpc.this.id }
output "vpc_cidr" { value = aws_vpc.this.cidr_block }
output "public_subnet_ids" { value = values(aws_subnet.public)[*].id }
output "application_subnet_ids" { value = values(aws_subnet.application)[*].id }
output "data_subnet_ids" { value = values(aws_subnet.data)[*].id }
output "nat_gateway_ids" { value = values(aws_nat_gateway.this)[*].id }
