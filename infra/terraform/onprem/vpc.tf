resource "aws_vpc" "onprem" {
  cidr_block           = var.onprem_vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.common_tags, { Name = "${var.project_name}-onprem" })
}

resource "aws_internet_gateway" "onprem" {
  vpc_id = aws_vpc.onprem.id
  tags   = merge(local.common_tags, { Name = "${var.project_name}-onprem-igw" })
}
