output "bind_private_ip" {
  value       = aws_instance.bind.private_ip
  description = "MasterDns for Lambda / AXFR target"
}

output "bind_instance_id" {
  value       = aws_instance.bind.id
  description = "Use with SSM Session Manager in the on-prem account"
}

output "vpn_appliance_public_ip" {
  value       = aws_eip.vpn_appliance.public_ip
  description = "Customer gateway IP (workload account CGW target)"
}

output "onprem_vpc_id" {
  value = aws_vpc.onprem.id
}

output "onprem_vpc_cidr" {
  value = var.onprem_vpc_cidr
}

output "vpn_appliance_instance_id" {
  value       = try(aws_instance.vpn_appliance[0].id, null)
  description = "Use with SSM Session Manager in the on-prem account (null until workload VPN exists)"
}

output "onprem_instance_id" {
  value       = try(aws_instance.onprem_test[0].id, null)
  description = "Optional on-prem test instance"
}
