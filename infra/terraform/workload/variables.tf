variable "aws_region" {
  type        = string
  default     = "ap-southeast-2"
  description = "AWS region (default: Sydney)"
}

variable "aws_profile" {
  type        = string
  description = "AWS CLI profile for the workload account"
  default     = "bind-demo-workload"
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
  description = "CIDR for OnPrem_VPC in the on-prem account"
}

variable "workload_vpc_cidr" {
  type        = string
  default     = "10.1.0.0/16"
  description = "CIDR for Workload_VPC (created in this account)"
}

variable "onprem_state_path" {
  type        = string
  description = "Path to on-prem stack terraform.tfstate (for CGW IP and MasterDns)"
  default     = ""
}

variable "sync_interval_minutes" {
  type    = number
  default = 15
}

variable "ignore_ttl" {
  type    = bool
  default = true
}
