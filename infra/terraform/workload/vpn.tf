resource "aws_customer_gateway" "onprem" {
  bgp_asn    = 65000
  ip_address = data.terraform_remote_state.onprem.outputs.vpn_appliance_public_ip
  type       = "ipsec.1"
  tags       = merge(local.common_tags, { Name = "${var.project_name}-cgw" })
}

resource "aws_vpn_gateway" "workload" {
  vpc_id = aws_vpc.workload.id
  tags   = merge(local.common_tags, { Name = "${var.project_name}-vgw" })
}

resource "aws_vpn_gateway_attachment" "workload" {
  vpc_id         = aws_vpc.workload.id
  vpn_gateway_id = aws_vpn_gateway.workload.id
}

resource "aws_vpn_connection" "onprem" {
  vpn_gateway_id      = aws_vpn_gateway.workload.id
  customer_gateway_id = aws_customer_gateway.onprem.id
  type                = "ipsec.1"
  static_routes_only  = true

  # Libreswan 4.x on AL2023 rejects modp1024 (AWS default); use DH group 14.
  tunnel1_phase1_encryption_algorithms = ["AES256"]
  tunnel1_phase1_integrity_algorithms  = ["SHA2-256"]
  tunnel1_phase1_dh_group_numbers      = [14]
  tunnel1_phase2_encryption_algorithms = ["AES256"]
  tunnel1_phase2_integrity_algorithms  = ["SHA2-256"]
  tunnel1_phase2_dh_group_numbers      = [14]
  tunnel1_ike_versions                 = ["ikev1"]

  tags = merge(local.common_tags, { Name = "${var.project_name}-vpn" })
}

resource "aws_vpn_connection_route" "onprem" {
  destination_cidr_block = data.terraform_remote_state.onprem.outputs.onprem_vpc_cidr
  vpn_connection_id      = aws_vpn_connection.onprem.id
}

resource "aws_route" "workload_to_onprem" {
  route_table_id         = aws_route_table.workload_private.id
  destination_cidr_block = data.terraform_remote_state.onprem.outputs.onprem_vpc_cidr
  gateway_id             = aws_vpn_gateway.workload.id
  depends_on             = [aws_vpn_gateway_attachment.workload]
}
