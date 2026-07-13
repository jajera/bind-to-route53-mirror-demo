# AL2023 package metadata and RPMs are stored in S3. The bind subnet has no IGW/NAT,
# so a gateway endpoint is required for dnf on first boot.
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.onprem.id
  service_name = "com.amazonaws.${var.aws_region}.s3"

  route_table_ids = [
    aws_route_table.onprem_bind.id,
  ]

  tags = merge(local.common_tags, { Name = "${var.project_name}-s3" })
}
