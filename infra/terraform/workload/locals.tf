locals {
  bind_subnet_cidr   = cidrsubnet(var.onprem_vpc_cidr, 8, 1)
  lambda_subnet_cidr = cidrsubnet(var.workload_vpc_cidr, 8, 1)
  test_subnet_cidr   = cidrsubnet(var.workload_vpc_cidr, 8, 2)

  onprem_state_path = var.onprem_state_path != "" ? var.onprem_state_path : abspath("${path.module}/../onprem/terraform.tfstate")

  common_tags = {
    Project = var.project_name
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  # Standard AL2023 (includes amazon-ssm-agent). Avoid *-minimal-* which has no SSM agent.
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}
