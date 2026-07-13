# Implementation Plan: BIND-to-Route 53 Mirror Demo

## Overview

This plan aligns implementation with the current requirements and design:

- Two VPCs (`OnPrem_VPC`, `Workload_VPC`)
- Site-to-Site VPN (VGW + customer gateway via `VPN_Appliance`)
- BIND on EC2 as source of truth
- VPC-attached Lambda for AXFR -> normalize -> diff -> apply
- Route 53 private hosted zone attached to `Workload_VPC` only
- Validation from `Test_Instance` via AmazonProvidedDNS

The work is split into 3 tracks:

1. **Infrastructure track** (Req 6-10, 15, 18)
2. **Application track** (Req 1-5, 11-17)
3. **Validation/docs track** (Req 14, 16-18)

---

## Delivery Milestones

- [x] **M1: Network-ready environment**
  - VPN tunnel UP, routing works, BIND reachable from Lambda subnet on TCP 53.
- [x] **M2: Sync pipeline feature complete**
  - Handler performs full flow with logging and error behavior.
- [x] **M3: Test-complete implementation**
  - Property/unit/integration tests pass.
- [x] **M4: Demo-ready walkthrough**
  - End-to-end scenario documented and reproducible.

---

## Stack defaults (decisions, not tasks)

These were open questions in requirements/design; the demo stack uses:

| Setting | Default | Rationale |
| --- | --- | --- |
| `OnPrem_Instance` | **Optional** (off in minimal stack) | Req 8; proves BIND authority when enabled |
| `IgnoreTTL` | **`true`** | Fewer UPSERTs from TTL-only drift in lab zones |
| `BIND_EC2` vs `VPN_Appliance` | **Separate EC2s** | CGW needs public IP; BIND stays private |
| Manual "sync now" | **Included** | Lambda test invoke + doc step; avoids waiting 15 min during first validation |
| Python | **3.14** | Latest Lambda-supported; local/CI on 3.14; deploy with runtime `python3.14` |

Change these in IaC/EventBridge payload only if you intentionally want different demo behavior.

---

## Tasks

### 1) Create infrastructure baseline (two VPC + VPN)

- [x] 1.1 Define IaC layout for network and compute
  - Create modules/stacks for `OnPrem_VPC`, `Workload_VPC`, VPN, EC2, Lambda, Route 53
  - Enforce non-overlapping CIDRs
  - _Requirements: 6.1, 10.1_

- [x] 1.2 Provision `OnPrem_VPC` resources
  - Create `BIND_EC2` (private IP, no public DNS exposure)
  - Create `VPN_Appliance` EC2 with public IP for customer gateway
  - Optionally create `OnPrem_Instance`
  - _Requirements: 6.2, 7.1, 7.2, 7.4, 8_

- [x] 1.3 Provision `Workload_VPC` resources
  - Create private subnets for Lambda ENIs
  - Attach Virtual Private Gateway
  - Create `Test_Instance`
  - _Requirements: 6.3, 10.5, 14_

- [x] 1.4 Provision Site-to-Site VPN and routing
  - Create Customer Gateway referencing `VPN_Appliance`
  - Create VPN connection and at least one tunnel in `UP` state
  - Configure routes both directions
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 1.5 Configure security boundaries
  - Allow TCP 53 from Lambda subnet CIDR to `BIND_EC2` only
  - Deny broad ingress to DNS ports from internet
  - Ensure no VPC peering exists between the two VPCs
  - _Requirements: 6.5, 7.3, 7.4, 9.1, 10.8_

- [x] 1.6 Configure Route 53 private hosted zone
  - Create `corp.internal` private zone
  - Associate with `Workload_VPC` only
  - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [x] 1.7 Configure Lambda outbound path to Route 53 API
  - NAT gateway or VPC interface endpoint
  - _Requirements: 10.6_

### 2) Configure BIND on EC2

- [x] 2.1 Install and configure BIND as authoritative master for `corp.internal`
- [x] 2.2 Add `allow-transfer` ACL for Lambda subnet CIDR only
- [x] 2.3 Create baseline zone file and reload/restart named
- [x] 2.4 Add validation commands in docs (`dig`, `rndc reload`, transfer refusal checks)
- _Requirements: 7.1, 7.5, 9.1, 9.2, 9.3_

### 3) Set up Python project and core models

- [x] 3.1 Create Python package/module layout
  - `src/zone_sync/`, `tests/`, `tests/integration/`
  - Pin **Python 3.14** (e.g. `.python-version` `3.14`, `requires-python = ">=3.14,<3.15"`)
- [x] 3.2 Add dependencies
  - runtime: `dnspython`, `boto3` (Python 3.14)
  - dev: `pytest`, `hypothesis`, `moto[route53]`
- [x] 3.3 Implement data models/constants/exceptions
  - `RecordKey`, `RecordSet`, `RawRecord`, `ValidatedInput`, `DiffResult`, `ApplyResult`
  - `SYNC_TYPES`, `MAX_BATCH_SIZE`, `DEFAULT_TIMEOUT`
  - `ValidationError`, `AXFRError`, `Route53ReadError`, `ApplyError`
- _Requirements: 1-5, 13_

### 4) Implement sync pipeline modules

- [x] 4.1 Implement `validator.py`
  - Validate `Domain`, `MasterDns`, `ZoneId`, `IgnoreTTL`
  - _Requirements: 13.1, 13.2, 13.3, 13.4_

- [x] 4.2 Implement `axfr_client.py`
  - Full AXFR via `dnspython`; convert to `RawRecord`
  - Raise clear errors for timeout/refused/connection issues
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 4.3 Implement `route53_reader.py`
  - Paginate `ListResourceRecordSets`
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 4.4 Implement `normalizer.py`
  - Trailing dots, TXT normalization, type filtering, malformed skip
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 1.4_

- [x] 4.5 Implement `diff_engine.py`
  - CREATE/UPSERT/DELETE, apex NS+SOA exclusions, CNAME conflicts
  - Empty diff behavior
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

- [x] 4.6 Implement `applicator.py`
  - No-op on empty diff, batch <=1000, apply counts/errors
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 4.7 Implement `sync_logger.py`
  - Structured logs: start/success/warnings/errors and stage tags (`validation|vpn|axfr|r53_read|r53_write`)
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [x] 4.8 Implement `handler.py` orchestration
  - validate -> AXFR -> read -> normalize -> diff -> apply -> log
  - Ensure AXFR failure never triggers Route 53 writes
  - _Requirements: 1-5, 13, 16, 17_

### 5) Configure Lambda runtime and schedule

- [x] 5.1 Deploy Lambda in private subnet(s) in `Workload_VPC` with runtime **`python3.14`**
- [x] 5.2 Attach least-privilege execution role
- [x] 5.3 Create EventBridge schedule (default 15 min)
- [x] 5.4 Pass payload: `Domain`, `MasterDns`, `ZoneId`, `IgnoreTTL: true` (per stack defaults)
- [x] 5.5 Document manual Lambda test invoke as "sync now" for lab validation
- _Requirements: 11, 12_

### 6) Test implementation (property, unit, integration)

- [x] 6.1 Property tests (Hypothesis)
  - Normalizer properties: 1,2,3,4,14
  - Diff properties: 5,6,7,8,9,10,12
  - Validator property: 13
  - Batcher property: 11

- [x] 6.2 Unit tests per module
  - validator, axfr_client, route53_reader, normalizer, diff_engine, applicator, logger, handler

- [x] 6.3 Integration tests with moto
  - Full create/update/delete and idempotency
  - CNAME conflict behavior

- [x] 6.4 Smoke tests against deployed stack
  - AXFR over VPN works from Lambda subnet
  - Route 53 API access works from Lambda subnet
- _Requirements: 1-5, 10, 13, 16, 17_

### 7) End-to-end demo validation

- [x] 7.1 Confirm VPN tunnel is `UP`
- [x] 7.2 Change record on `BIND_EC2`; reload named
- [x] 7.3 If `OnPrem_Instance` is deployed, verify immediate answer from BIND
- [x] 7.4 Run manual "sync now" invoke, or wait one `Sync_Interval` + runtime
- [x] 7.5 Query from `Test_Instance` via AmazonProvidedDNS
- [x] 7.6 Validate delete behavior (NXDOMAIN/empty response)
- [x] 7.7 Confirm logs include start, batch counts, duration, warning/error detail
- _Requirements: 10.2, 14, 16, 18_

### 8) Documentation and operator guidance

- [x] 8.1 Update architecture and deployment docs
  - Diagram with OnPrem_VPC, Workload_VPC, VGW, VPN_Appliance, Route53_Zone
- [x] 8.2 Add runbook for tunnel checks and common failures
  - tunnel down, AXFR refusal, Route 53 API issues
- [x] 8.3 Add cost note and teardown guidance
  - VPN ~`$0.05/hr` (~`$1.20/day`) while provisioned
- [x] 8.4 Add clear statement of non-goals and production gaps
- _Requirements: 17.3, 17.4, 17.5, 18.1-18.6_

### 9) Final exit checklist

- [x] 9.1 All tests passing locally/CI
- [x] 9.2 At least one successful full sync in deployed environment
- [x] 9.3 Failure scenario validated (VPN down or AXFR blocked) with expected behavior
- [x] 9.4 Requirements traceability checked (Req 1-18 covered)

---

## Notes

- **`OnPrem_Instance`** is optional in the default stack; enable via IaC when you want Req 8 validation.
- Prioritize infrastructure readiness (Tasks 1-2) before deep application debugging.
- Keep `Test_Instance` resolver configuration untouched (must use AmazonProvidedDNS).
- Avoid introducing VPC peering between demo VPCs.
- Use **Python 3.14** for local/CI; deploy Sync_Lambda on AWS **`python3.14`** runtime (latest supported).

---

## Suggested Execution Order

```text
Wave 1: Tasks 1-2 (network + BIND + VPN)
Wave 2: Tasks 3-4 (application code)
Wave 3: Task 5 (lambda deploy + schedule)
Wave 4: Task 6 (tests)
Wave 5: Tasks 7-8 (e2e validation + docs)
Wave 6: Task 9 (exit checklist)
```
