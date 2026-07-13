resource "aws_eip" "vpn_appliance" {
  domain = "vpc"
  tags   = merge(local.common_tags, { Name = "${var.project_name}-vpn-eip" })
}

resource "aws_security_group" "vpn_appliance" {
  name        = "${var.project_name}-vpn-appliance"
  description = "Site-to-Site VPN appliance (customer gateway endpoint)"
  vpc_id      = aws_vpc.onprem.id

  ingress {
    description = "IPsec UDP 500"
    from_port   = 500
    to_port     = 500
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "IPsec UDP 4500"
    from_port   = 4500
    to_port     = 4500
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "ESP"
    from_port   = 0
    to_port     = 0
    protocol    = "50"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

# Created only after the workload stack exposes VPN tunnel outputs (via remote state).
# Avoids bootstrap vs configured user_data flips that replace the instance every apply.
resource "aws_instance" "vpn_appliance" {
  count = local.vpn_tunnel_ready ? 1 : 0

  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.onprem_vpn.id
  vpc_security_group_ids      = [aws_security_group.vpn_appliance.id]
  source_dest_check           = false
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.ssm.name

  user_data = templatefile("${path.module}/../templates/vpn-appliance-user-data.sh.tpl", {
    local_public_ip        = aws_eip.vpn_appliance.public_ip
    workload_cidr          = var.workload_vpc_cidr
    onprem_cidr            = var.onprem_vpc_cidr
    tunnel_outside_address = local.vpn_tunnel_outside_address
    preshared_key          = local.vpn_tunnel_preshared_key
  })
  user_data_replace_on_change = true

  tags = merge(local.common_tags, { Name = "${var.project_name}-vpn-appliance" })
}

resource "aws_eip_association" "vpn_appliance" {
  count = local.vpn_tunnel_ready ? 1 : 0

  allocation_id = aws_eip.vpn_appliance.id
  instance_id   = aws_instance.vpn_appliance[0].id
}

resource "aws_route" "onprem_vpn_to_workload" {
  count = local.vpn_tunnel_ready ? 1 : 0

  route_table_id         = aws_route_table.onprem_vpn.id
  destination_cidr_block = var.workload_vpc_cidr
  network_interface_id   = aws_instance.vpn_appliance[0].primary_network_interface_id
}

resource "aws_route" "onprem_bind_to_workload" {
  count = local.vpn_tunnel_ready ? 1 : 0

  route_table_id         = aws_route_table.onprem_bind.id
  destination_cidr_block = var.workload_vpc_cidr
  network_interface_id   = aws_instance.vpn_appliance[0].primary_network_interface_id
  depends_on             = [aws_instance.vpn_appliance]
}
