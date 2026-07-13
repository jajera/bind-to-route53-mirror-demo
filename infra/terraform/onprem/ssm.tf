data "aws_iam_policy_document" "ssm_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ssm" {
  name               = "${var.project_name}-ssm"
  assume_role_policy = data.aws_iam_policy_document.ssm_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm" {
  name = "${var.project_name}-ssm"
  role = aws_iam_role.ssm.name
}

resource "aws_security_group" "ssm_endpoints" {
  name        = "${var.project_name}-ssm-endpoints"
  description = "Systems Manager interface endpoints"
  vpc_id      = aws_vpc.onprem.id

  ingress {
    description = "HTTPS from on-prem VPC"
    from_port   = 443
    to_port     = 443
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

resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = aws_vpc.onprem.id
  service_name        = "com.amazonaws.${var.aws_region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.onprem_bind.id]
  security_group_ids  = [aws_security_group.ssm_endpoints.id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "ec2messages" {
  vpc_id              = aws_vpc.onprem.id
  service_name        = "com.amazonaws.${var.aws_region}.ec2messages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.onprem_bind.id]
  security_group_ids  = [aws_security_group.ssm_endpoints.id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "ssmmessages" {
  vpc_id              = aws_vpc.onprem.id
  service_name        = "com.amazonaws.${var.aws_region}.ssmmessages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.onprem_bind.id]
  security_group_ids  = [aws_security_group.ssm_endpoints.id]
  private_dns_enabled = true
}
