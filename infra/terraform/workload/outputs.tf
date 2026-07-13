output "bind_private_ip" {
  value       = data.terraform_remote_state.onprem.outputs.bind_private_ip
  description = "MasterDns (BIND in on-prem account)"
}

output "route53_zone_id" {
  value = aws_route53_zone.private.zone_id
}

output "sync_lambda_name" {
  value = aws_lambda_function.sync.function_name
}

output "test_instance_id" {
  value       = aws_instance.test.id
  description = "Use with SSM Session Manager in the workload account"
}

output "test_instance_public_ip" {
  value = aws_instance.test.public_ip
}

output "vpn_connection_id" {
  value = aws_vpn_connection.onprem.id
}

output "workload_vpc_id" {
  value = aws_vpc.workload.id
}

output "vpn_tunnel_outside_address" {
  value = aws_vpn_connection.onprem.tunnel1_address
}

output "vpn_tunnel_preshared_key" {
  value     = aws_vpn_connection.onprem.tunnel1_preshared_key
  sensitive = true
}
