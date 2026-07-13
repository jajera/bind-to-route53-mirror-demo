#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ONPREM="$ROOT/infra/terraform/onprem"
WORKLOAD="$ROOT/infra/terraform/workload"

echo "==> Destroy workload account stack"
terraform -chdir="$WORKLOAD" destroy "$@"

echo "==> Destroy on-prem account stack"
terraform -chdir="$ONPREM" destroy "$@"
