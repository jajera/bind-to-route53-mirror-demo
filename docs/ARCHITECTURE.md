# Architecture

## Topology (cross-account)

Open [`docs/diagrams/architecture.drawio`](diagrams/architecture.drawio) in [diagrams.net](https://app.diagrams.net/) (dark-mode aware, official [AWS Architecture Icons](https://jajera.github.io/aws-icons)).

## Traffic paths

| Flow | Path |
| --- | --- |
| AXFR | Lambda → VGW → VPN → VPN appliance → BIND |
| Route 53 API | Lambda → NAT gateway → Route 53 (HTTPS) |
| Workload DNS | Test instance → VPC+2 resolver → Route 53 mirror |

## Sync pipeline

1. EventBridge invokes Lambda with `Domain`, `MasterDns`, `ZoneId`, `IgnoreTTL`.
2. AXFR full zone from BIND (on-prem account, over VPN).
3. List Route 53 records.
4. Normalize, diff, apply batched changes (≤1000 per call).
5. Structured logs to CloudWatch.

## Non-goals and production gaps

This demo is a reference architecture, not a production DNS product. The following are explicitly out of scope:

- No VPC peering (Site-to-Site VPN only)
- No public delegation of `corp.internal`
- No IXFR — full AXFR zone transfer only (no incremental)
- No bi-directional sync (Route 53 → BIND not supported)
- No high availability (HA) or multi-region failover for BIND or Lambda
- No redundant tunnels — only one VPN tunnel used in this demo
- No change approval workflow for BIND zone edits (direct SSM session + reload)
- No automated rollback of bad BIND changes or failed syncs
- No real-time sync — scheduled batch only (default 15-minute interval)
- No multi-zone support beyond the single `corp.internal` demo zone
