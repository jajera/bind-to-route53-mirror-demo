#!/bin/bash
set -ux

# AL2023 repos are on S3; the bind subnet reaches S3 via a gateway VPC endpoint (no internet).
for attempt in $(seq 1 12); do
  if dnf -y install bind bind-utils; then
    break
  fi
  echo "dnf attempt $attempt failed, retrying in 15s..."
  sleep 15
done
if ! rpm -q bind bind-utils >/dev/null 2>&1; then
  echo "bind packages not installed after retries" >&2
  exit 1
fi

set -e
systemctl enable named
TOKEN=$(curl -sf -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
BIND_IP=$(curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/local-ipv4)
test -n "$BIND_IP"

cat >/etc/named.conf <<EOF
options {
    directory "/var/named";
    listen-on port 53 { any; };
    allow-query { any; };
    recursion no;
    dnssec-validation no;
};

zone "${domain_name}" {
    type master;
    file "/var/named/${domain_name}.zone";
    allow-transfer { ${allow_transfer_cidr}; };
};
EOF

cat >/var/named/${domain_name}.zone <<EOF
\$TTL 300
@   IN SOA ns1.${domain_name}. admin.${domain_name}. (
        2026010101 ; serial
        3600       ; refresh
        600        ; retry
        86400      ; expire
        300 )      ; minimum
    IN NS  ns1.${domain_name}.
ns1 IN A   $${BIND_IP}
app IN A   10.0.1.50
EOF

named-checkconf
named-checkzone ${domain_name} /var/named/${domain_name}.zone
systemctl restart named
