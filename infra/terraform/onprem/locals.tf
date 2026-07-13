locals {
  bind_subnet_cidr   = cidrsubnet(var.onprem_vpc_cidr, 8, 1)
  vpn_subnet_cidr    = cidrsubnet(var.onprem_vpc_cidr, 8, 2)
  lambda_subnet_cidr = cidrsubnet(var.workload_vpc_cidr, 8, 1)

  workload_state_path = var.workload_state_path != "" ? var.workload_state_path : abspath("${path.module}/../workload/terraform.tfstate")

  vpn_tunnel_outside_address = var.vpn_tunnel_outside_address != "" ? var.vpn_tunnel_outside_address : try(
    data.terraform_remote_state.workload[0].outputs.vpn_tunnel_outside_address,
    ""
  )
  vpn_tunnel_preshared_key = var.vpn_tunnel_preshared_key != "" ? var.vpn_tunnel_preshared_key : try(
    data.terraform_remote_state.workload[0].outputs.vpn_tunnel_preshared_key,
    ""
  )
  vpn_tunnel_ready = local.vpn_tunnel_outside_address != "" && local.vpn_tunnel_preshared_key != ""

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
