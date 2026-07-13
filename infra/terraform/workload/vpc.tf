resource "aws_vpc" "workload" {
  cidr_block           = var.workload_vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.common_tags, { Name = "${var.project_name}-workload" })
}

resource "aws_internet_gateway" "workload" {
  vpc_id = aws_vpc.workload.id
  tags   = merge(local.common_tags, { Name = "${var.project_name}-workload-igw" })
}

resource "aws_subnet" "workload_public" {
  vpc_id                  = aws_vpc.workload.id
  cidr_block              = cidrsubnet(var.workload_vpc_cidr, 8, 10)
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = merge(local.common_tags, { Name = "${var.project_name}-workload-public" })
}

resource "aws_subnet" "workload_lambda" {
  vpc_id            = aws_vpc.workload.id
  cidr_block        = local.lambda_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[0]
  tags              = merge(local.common_tags, { Name = "${var.project_name}-workload-lambda" })
}

resource "aws_subnet" "workload_test" {
  vpc_id            = aws_vpc.workload.id
  cidr_block        = local.test_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[0]
  tags              = merge(local.common_tags, { Name = "${var.project_name}-workload-test" })
}

resource "aws_route_table" "workload_private" {
  vpc_id = aws_vpc.workload.id
  tags   = merge(local.common_tags, { Name = "${var.project_name}-workload-private-rt" })
}

resource "aws_route_table" "workload_public" {
  vpc_id = aws_vpc.workload.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.workload.id
  }

  tags = merge(local.common_tags, { Name = "${var.project_name}-workload-public-rt" })
}

resource "aws_route_table_association" "workload_lambda" {
  subnet_id      = aws_subnet.workload_lambda.id
  route_table_id = aws_route_table.workload_private.id
}

resource "aws_route_table_association" "workload_test" {
  subnet_id      = aws_subnet.workload_test.id
  route_table_id = aws_route_table.workload_private.id
}

resource "aws_route_table_association" "workload_public" {
  subnet_id      = aws_subnet.workload_public.id
  route_table_id = aws_route_table.workload_public.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = local.common_tags
}

resource "aws_nat_gateway" "workload" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.workload_public.id
  tags          = merge(local.common_tags, { Name = "${var.project_name}-nat" })
  depends_on    = [aws_internet_gateway.workload]
}

resource "aws_route" "workload_nat" {
  route_table_id         = aws_route_table.workload_private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.workload.id
}

resource "aws_security_group" "test" {
  name        = "${var.project_name}-test"
  description = "Test instance"
  vpc_id      = aws_vpc.workload.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_instance" "test" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.workload_test.id
  vpc_security_group_ids      = [aws_security_group.test.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.ssm.name

  tags = merge(local.common_tags, { Name = "${var.project_name}-test" })
}
