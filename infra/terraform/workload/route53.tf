resource "aws_route53_zone" "private" {
  name          = var.domain_name
  force_destroy = true

  vpc {
    vpc_id = aws_vpc.workload.id
  }

  tags = merge(local.common_tags, { Name = "${var.project_name}-private-zone" })
}
