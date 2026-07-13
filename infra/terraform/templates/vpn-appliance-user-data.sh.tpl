#!/bin/bash
set -eux
sysctl -w net.ipv4.ip_forward=1
grep -q '^net.ipv4.ip_forward' /etc/sysctl.conf || echo "net.ipv4.ip_forward = 1" >>/etc/sysctl.conf

# AL2023 images do not ship iptables by default; required for FORWARD transit rules.
dnf install -y libreswan iptables
systemctl enable ipsec

# Docker/AL2023 may set FORWARD policy DROP; allow cross-VPC transit via this appliance.
iptables -I FORWARD 1 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -I FORWARD 2 -s ${workload_cidr} -d ${onprem_cidr} -j ACCEPT
iptables -I FORWARD 3 -s ${onprem_cidr} -d ${workload_cidr} -j ACCEPT

cat >/etc/ipsec.d/aws.conf <<EOF
conn aws-tunnel-1
    auto=start
    authby=secret
    type=tunnel
    encapsulation=yes
    left=%defaultroute
    leftid=${local_public_ip}
    leftsubnet=${onprem_cidr}
    right=${tunnel_outside_address}
    rightid=${tunnel_outside_address}
    rightsubnet=${workload_cidr}
    ikev2=no
    ike=aes256-sha2_256;modp2048
    phase2alg=aes256-sha2_256;modp2048
    pfs=yes
    keylife=3600s
    ikelifetime=28800s
EOF

cat >/etc/ipsec.d/aws.secrets <<EOF
${local_public_ip} ${tunnel_outside_address} : PSK "${preshared_key}"
EOF
chmod 600 /etc/ipsec.d/aws.secrets

systemctl restart ipsec
sleep 5
ipsec status | grep -E 'Total IPsec|"aws-tunnel-1"' || true
