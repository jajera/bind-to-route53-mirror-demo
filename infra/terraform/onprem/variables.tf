variable "aws_region" {
  type        = string
  default     = "ap-southeast-2"
  description = "AWS region (default: Sydney)"
}

variable "aws_profile" {
  type        = string
  description = "AWS CLI profile for the simulated on-prem account"
  default     = "bind-demo-onprem"
}

variable "project_name" {
  type    = string
  default = "bind-route53-demo"
}

variable "domain_name" {
  type    = string
  default = "corp.internal"
}

variable "onprem_vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "CIDR for OnPrem_VPC (created in this account)"
}

variable "workload_vpc_cidr" {
  type        = string
  default     = "10.1.0.0/16"
  description = "CIDR for Workload_VPC in the workload account (for VPN routes)"
}

variable "workload_state_path" {
  type        = string
  description = "Path to workload stack terraform.tfstate (for VPN tunnel outputs)"
  default     = ""
}

variable "enable_onprem_test_instance" {
  type    = bool
  default = false
}

# Set by scripts/deploy_stacks.sh after the workload stack creates the VPN connection.
variable "vpn_tunnel_outside_address" {
  type        = string
  description = "AWS VPN tunnel outside IP (from workload stack output)"
  default     = ""
}

variable "vpn_tunnel_preshared_key" {
  type        = string
  description = "IPsec pre-shared key (from workload stack output)"
  default     = ""
  sensitive   = true
}
