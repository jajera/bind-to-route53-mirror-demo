#!/bin/bash
# Deploy cross-account demo: on-prem account first, workload account second,
# then on-prem again to create the VPN appliance once tunnel outputs exist.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ONPREM="$ROOT/infra/terraform/onprem"
WORKLOAD="$ROOT/infra/terraform/workload"

echo "==> Building Lambda package (skipped if src/ unchanged; FORCE_LAMBDA_BUILD=1 to rebuild)"
"$ROOT/scripts/build_lambda.sh"

echo "==> [1/3] On-prem account (VPC, BIND, VPN EIP — appliance after workload VPN)"
terraform -chdir="$ONPREM" init -input=false
terraform -chdir="$ONPREM" apply "$@"

echo "==> [2/3] Workload account (VPC, VGW, VPN, Lambda, Route 53)"
terraform -chdir="$WORKLOAD" init -input=false
terraform -chdir="$WORKLOAD" apply "$@"

echo "==> [3/3] On-prem account (VPN appliance reads tunnel config from workload state)"
terraform -chdir="$ONPREM" apply "$@"

echo "==> Deploy complete"
echo "    On-prem profile:  bind-demo-onprem"
echo "    Workload profile: bind-demo-workload"
echo "    bind_private_ip:  $(terraform -chdir="$ONPREM" output -raw bind_private_ip)"
echo "    sync_lambda_name: $(terraform -chdir="$WORKLOAD" output -raw sync_lambda_name)"
