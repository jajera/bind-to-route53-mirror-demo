resource "aws_subnet" "onprem_bind" {
  vpc_id                  = aws_vpc.onprem.id
  cidr_block              = local.bind_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false
  tags                    = merge(local.common_tags, { Name = "${var.project_name}-onprem-bind" })
}

resource "aws_subnet" "onprem_vpn" {
  vpc_id                  = aws_vpc.onprem.id
  cidr_block              = local.vpn_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = merge(local.common_tags, { Name = "${var.project_name}-onprem-vpn" })
}

resource "aws_route_table" "onprem_bind" {
  vpc_id = aws_vpc.onprem.id
  tags   = merge(local.common_tags, { Name = "${var.project_name}-onprem-bind-rt" })
}

resource "aws_route_table" "onprem_vpn" {
  vpc_id = aws_vpc.onprem.id
  tags   = merge(local.common_tags, { Name = "${var.project_name}-onprem-vpn-rt" })
}

resource "aws_route" "onprem_vpn_default" {
  route_table_id         = aws_route_table.onprem_vpn.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.onprem.id
}

resource "aws_route_table_association" "onprem_bind" {
  subnet_id      = aws_subnet.onprem_bind.id
  route_table_id = aws_route_table.onprem_bind.id
}

resource "aws_route_table_association" "onprem_vpn" {
  subnet_id      = aws_subnet.onprem_vpn.id
  route_table_id = aws_route_table.onprem_vpn.id
}

resource "aws_security_group" "bind" {
  name        = "${var.project_name}-bind"
  description = "BIND master"
  vpc_id      = aws_vpc.onprem.id

  ingress {
    description = "DNS AXFR from Lambda subnet (workload account via VPN)"
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = [local.lambda_subnet_cidr]
  }

  ingress {
    description = "DNS UDP from on-prem VPC"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = [var.onprem_vpc_cidr]
  }

  ingress {
    description = "DNS TCP from on-prem VPC"
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = [var.onprem_vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_instance" "bind" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.onprem_bind.id
  vpc_security_group_ids = [aws_security_group.bind.id]
  iam_instance_profile   = aws_iam_instance_profile.ssm.name

  user_data = templatefile("${path.module}/../templates/bind-user-data.sh.tpl", {
    domain_name         = var.domain_name
    allow_transfer_cidr = local.lambda_subnet_cidr
  })
  user_data_replace_on_change = true

  depends_on = [aws_vpc_endpoint.s3]

  tags = merge(local.common_tags, { Name = "${var.project_name}-bind" })
}

resource "aws_instance" "onprem_test" {
  count = var.enable_onprem_test_instance ? 1 : 0

  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.onprem_bind.id
  vpc_security_group_ids = [aws_security_group.onprem_test[0].id]
  iam_instance_profile   = aws_iam_instance_profile.ssm.name

  user_data = templatefile("${path.module}/../templates/onprem-test-user-data.sh.tpl", {
    bind_ip = aws_instance.bind.private_ip
  })

  tags = merge(local.common_tags, { Name = "${var.project_name}-onprem-test" })
}

resource "aws_security_group" "onprem_test" {
  count = var.enable_onprem_test_instance ? 1 : 0

  name        = "${var.project_name}-onprem-test"
  description = "Optional on-prem validation instance"
  vpc_id      = aws_vpc.onprem.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}
