# BIND-to-Route 53 Mirror Demo

Hybrid DNS demo: **BIND on EC2** (simulated on-prem account) mirrors into a **Route 53 private hosted zone** in a separate **workload account**, connected by **Site-to-Site VPN**, driven by a scheduled **Python 3.14** Lambda.

## Architecture

- **On-prem account** — `OnPrem_VPC` with `BIND_EC2`, `VPN_Appliance` (customer gateway IP)
- **Workload account** — `Workload_VPC` with `Sync_Lambda`, `Test_Instance`, Route 53 private zone
- **Site-to-Site VPN** — AXFR crosses the tunnel; Route 53 API uses NAT gateway (HTTPS)

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [`docs/diagrams/architecture.drawio`](docs/diagrams/architecture.drawio), and the operator path in [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md).

## AWS profiles

Configure two CLI profiles (same region, different accounts):

| Profile | Account role |
| --- | --- |
| `bind-demo-onprem` | Simulated on-prem (BIND + VPN appliance) |
| `bind-demo-workload` | AWS workloads (Lambda, Route 53, VGW) |

Override in Terraform with `-var='aws_profile=...'` if you use different names.

Set `region = ap-southeast-2` in both profiles (default).

## Quick start

### 1. Python sync code (local)

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/ -v
```

### 2. Deploy infrastructure

```bash
./scripts/deploy_stacks.sh
```

Optional: pass Terraform vars, e.g. `./scripts/deploy_stacks.sh -var='enable_onprem_test_instance=true'` (on-prem stack).

### 3. Validate demo

Follow [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) (VPN → BIND edit → Lambda sync → dig).

Details and smoke tests: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Failures: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Cost note

Site-to-Site VPN ~**$0.05/hr** (~**$1.20/day**) while provisioned. Tear down when idle:

```bash
./scripts/destroy_stacks.sh
```

## Project layout

```
src/zone_sync/              # Lambda sync pipeline (Python 3.14)
tests/                      # pytest + Hypothesis
dist/lambda/                # packaged Lambda artifact (generated)
infra/terraform/onprem/     # On-prem account stack
infra/terraform/workload/   # Workload account stack
docs/                       # Architecture, deployment, runbook
```

## Stack defaults

| Setting | Value |
| --- | --- |
| Python | 3.14 (`python3.14` Lambda runtime) |
| IgnoreTTL | `true` |
| Sync interval | 15 minutes |
| OnPrem test instance | optional (off by default) |
| On-prem CIDR | `10.0.0.0/16` |
| Workload CIDR | `10.1.0.0/16` |
| Region | `ap-southeast-2` (Sydney) |

## License

See [LICENSE](LICENSE).
