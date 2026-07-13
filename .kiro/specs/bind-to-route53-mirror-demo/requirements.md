# Requirements Document

## Introduction

This document defines the requirements for a **BIND-to-Route 53 zone mirroring demo** that keeps AWS workloads in sync with DNS records authored on a BIND master.

In production, BIND usually lives on-premises while workloads run in an AWS VPC, connected by **Site-to-Site VPN** (or Direct Connect). **This demo uses two VPCs in separate AWS accounts** (same region) to simulate that hybrid layout: the on-prem account stands in for the datacenter; the workload account stands in for AWS application land. **AWS Site-to-Site VPN** links them the way a real on-prem ↔ AWS deployment would—not VPC peering.

| VPC | Role |
|-----|------|
| **OnPrem_VPC** | Simulated on-premises: BIND_EC2 (DNS authority), optional OnPrem_Instance, and a VPN appliance EC2 acting as the customer gateway. |
| **Workload_VPC** | AWS application network: Virtual Private Gateway, Sync_Lambda, Test_Instance, and Route 53 private hosted zone association. |

Sync_Lambda (in Workload_VPC) AXFRs from BIND_EC2 (in OnPrem_VPC) over the **IPsec VPN tunnel** using BIND’s private IP. After sync, a record changed on BIND resolves on Test_Instance in Workload_VPC via AmazonProvidedDNS—even though that instance never talks to BIND directly.

This is intentionally a **demonstration and reference architecture**, not a production-grade DNS product. Requirements balance teaching value, hybrid-network realism, and a reproducible end-to-end path from BIND change to AWS VPC resolution.

---

## Business Context

### Problem Statement

Teams that split DNS authority (BIND) from compute (AWS) often face:

- **Drift** — Route 53 records fall out of date because updates are manual or ad hoc.
- **Blind spots** — Application owners change BIND; cloud teams discover mismatches only when something breaks.
- **Operational friction** — Every new service record requires a ticket, a human, and two systems to touch.

Mirroring BIND into a Route 53 private hosted zone gives AWS a **read-only replica** of internal DNS. BIND remains the single source of truth; AWS consumers get consistent resolution without re-delegating the zone publicly. The two-VPC + VPN layout makes the hybrid split visible: edit BIND in the simulated on-prem network, confirm AWS workloads pick it up after sync over the same VPN path production would use.

### Goals

1. **Single source of truth** — BIND master owns record lifecycle; Route 53 reflects it automatically.
2. **Predictable propagation** — Changes in BIND appear in Workload_VPC DNS within one sync interval under normal conditions.
3. **Hybrid realism** — Connectivity between OnPrem_VPC and Workload_VPC uses AWS Site-to-Site VPN, not VPC peering.
4. **Least privilege** — Zone transfer and API access are restricted to what the sync job needs.
5. **Observable behavior** — Operators can tell from logs whether a sync ran, what changed, and why something was skipped.
6. **Demonstrable end-to-end flow** — A reviewer can change a record on BIND_EC2, see it on BIND immediately, wait for sync, then resolve the same name from Test_Instance in Workload_VPC via Route 53.

### Non-Goals

- Replacing BIND as authoritative DNS for `corp.internal`.
- Public DNS delegation or internet-facing resolution of `corp.internal`.
- Real-time or sub-minute sync (scheduled batch sync is sufficient for this demo).
- Bi-directional sync (Route 53 → BIND) or conflict resolution beyond logging and skip.
- Supporting every DNS record type or exotic BIND features (see Requirement 4 scope).
- High availability, multi-region failover, or automated rollback of bad BIND changes.
- Physical on-premises hardware or Direct Connect.
- Transit Gateway (optional simplification: VPN terminates on Virtual Private Gateway in Workload_VPC).
- Cross-region VPN.
- A general-purpose DNS management UI or self-service portal.

---

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| **Infrastructure / platform engineer** | Builds the two-VPC topology, Site-to-Site VPN, sync pipeline, IAM, and BIND ACLs. |
| **Application team** | Expects internal hostnames in Workload_VPC to match what BIND publishes, without pointing instances at BIND directly. |
| **Security / compliance** | Wants encrypted hybrid connectivity, zone transfers locked down, no public BIND exposure, and auditable change logs. |
| **Demo reviewer / learner** | Needs a clear story: change BIND in on-prem VPC → sync over VPN → workload VPC resolves correctly. |

User stories below use these personas where it clarifies *who* benefits, not only *what* the Lambda does.

---

## Assumptions and Constraints

### Assumptions

- Demo stack deploys **two VPCs in separate AWS accounts** (same region): on-prem account and workload account.
- **Site-to-Site VPN** connects the accounts using a Virtual Private Gateway on the workload VPC and a software VPN appliance in the on-prem VPC as the customer gateway.
- **BIND_EC2** runs in OnPrem_VPC with a stable private IP used as the `MasterDns` Lambda input.
- **Sync_Lambda** runs in Workload_VPC (private subnet) and reaches BIND_EC2 over the VPN tunnel.
- **Route53_Zone** is a private hosted zone for `corp.internal` associated with **Workload_VPC only** (not OnPrem_VPC).
- **Test_Instance** runs in Workload_VPC and resolves `corp.internal` via AmazonProvidedDNS (Route 53 mirror)—not via BIND.
- Optional **OnPrem_Instance** in OnPrem_VPC resolves directly from BIND_EC2 to show the authoritative side of the demo.
- VPN connection is provisioned for the demo duration (~**$0.05/hr**, roughly **$1.20/day**); documentation SHALL recommend tearing down the stack when not in use.
- One BIND master per mirrored zone; secondary BIND servers are out of scope unless configured as the AXFR target.
- Sync frequency of **15 minutes by default** is acceptable for demo and lab use.
- Operators can SSH to BIND_EC2 and the VPN appliance (via bastion or Session Manager) to edit zone files and verify tunnel status.
- Demo traffic volume is low; AXFR payload size and Route 53 API limits are not a concern.

### Constraints

- Lambda must run inside Workload_VPC with a network path (VPN tunnel + routes + security groups) to BIND_EC2 in OnPrem_VPC.
- OnPrem_VPC and Workload_VPC CIDR blocks must not overlap (required for routable VPN connectivity).
- BIND_EC2 must not expose TCP/UDP 53 to the public internet; AXFR stays on private addresses reachable via the tunnel.
- AXFR is full-zone transfer only (no incremental IXFR in this demo).
- Route 53 manages apex NS records for the private zone; those must not be overwritten by sync logic.
- Internal zone names must not be published to public DNS.

---

## Glossary

- **OnPrem_VPC**: VPC simulating on-premises; hosts BIND_EC2, optional OnPrem_Instance, and VPN_Appliance.
- **Workload_VPC**: VPC simulating AWS application workloads; hosts Virtual Private Gateway, Sync_Lambda, Test_Instance, and Route 53 association for `corp.internal`.
- **Site_to_Site_VPN**: AWS managed IPsec VPN connection linking OnPrem_VPC to Workload_VPC.
- **Virtual_Private_Gateway**: AWS-side VPN endpoint attached to Workload_VPC.
- **Customer_Gateway**: Logical representation of the on-prem VPN endpoint; implemented by VPN_Appliance in this demo.
- **VPN_Appliance**: EC2 in OnPrem_VPC running IPsec software (for example strongSwan) to terminate the Site-to-Site VPN tunnel.
- **VPN_Tunnel**: Encrypted IPsec path carrying traffic (including AXFR) between Workload_VPC and OnPrem_VPC.
- **BIND_Master**: Authoritative BIND named server for `corp.internal`; runs on BIND_EC2 in OnPrem_VPC.
- **BIND_EC2**: EC2 in OnPrem_VPC running BIND; hosts zone files, listens on TCP/UDP 53, and is the AXFR source for Sync_Lambda.
- **OnPrem_Instance**: Optional EC2 in OnPrem_VPC configured to query BIND_EC2 directly; demonstrates authoritative DNS before mirroring.
- **AXFR**: Zone transfer over TCP port 53; Sync_Lambda pulls the full zone from BIND_EC2 across VPN_Tunnel.
- **Sync_Lambda**: Lambda in Workload_VPC that AXFRs from BIND_EC2, diffs against Route53_Zone, and applies changes.
- **Route53_Zone**: Route 53 private hosted zone for `corp.internal`, associated with Workload_VPC.
- **EventBridge_Schedule**: EventBridge rule triggering Sync_Lambda on a fixed interval (default: every 15 minutes).
- **Sync_Interval**: Time between Sync_Lambda invocations.
- **Record_Set**: Normalized DNS record (name, type, TTL, resource data) for comparison.
- **Change_Batch**: Group of `ChangeResourceRecordSets` operations per API call.
- **Test_Instance**: EC2 in Workload_VPC used to validate resolution via AmazonProvidedDNS against Route53_Zone.
- **Propagation_Delay**: Time from a BIND zone change until Test_Instance returns the updated answer; bounded by Sync_Interval plus sync execution time.

---

## Requirements

### Requirement 1: Zone Transfer from BIND Master

**User Story:** As a platform engineer, I want Sync_Lambda in Workload_VPC to pull the full zone via AXFR from BIND_EC2 in OnPrem_VPC over the VPN tunnel, so that every current DNS record is available for synchronization.

#### Acceptance Criteria

1. WHEN Sync_Lambda is invoked, THE Sync_Lambda SHALL perform an AXFR request to the BIND_EC2 private IP (`MasterDns`) on TCP port 53 for the configured domain.
2. WHEN the AXFR response is received, THE Sync_Lambda SHALL parse the response into a collection of Record_Set objects.
3. IF the AXFR request fails due to network timeout or connection refusal, THEN THE Sync_Lambda SHALL log the error to CloudWatch Logs and terminate the invocation with a non-zero exit status.
4. IF the AXFR response contains malformed or unparseable records, THEN THE Sync_Lambda SHALL log a warning for each malformed record and exclude that record from synchronization.
5. WHEN AXFR succeeds, THE Sync_Lambda SHALL log the total count of records parsed from the transfer.

---

### Requirement 2: Route 53 State Retrieval

**User Story:** As a platform engineer, I want Sync_Lambda to read the current Route 53 private hosted zone state, so that only real differences drive API changes.

#### Acceptance Criteria

1. WHEN Sync_Lambda has completed the AXFR parse, THE Sync_Lambda SHALL call `ListResourceRecordSets` on the configured Route53_Zone and retrieve all existing records.
2. WHEN the Route 53 response is received, THE Sync_Lambda SHALL parse the response into Record_Set objects using the same normalization as the AXFR result.
3. IF the `ListResourceRecordSets` API call fails, THEN THE Sync_Lambda SHALL log the error to CloudWatch Logs and terminate the invocation with a non-zero exit status.

---

### Requirement 3: Record Normalization

**User Story:** As a platform engineer, I want BIND and Route 53 records normalized to a common format, so that harmless formatting differences do not cause false updates.

#### Acceptance Criteria

1. THE Sync_Lambda SHALL normalize all record names to fully qualified domain names with a trailing dot.
2. THE Sync_Lambda SHALL normalize TXT record data by removing outer quotes and joining split strings into a single value for comparison.
3. THE Sync_Lambda SHALL compare records using type, name, and resource data as the composite key.
4. WHERE the IgnoreTTL input parameter is set to true, THE Sync_Lambda SHALL exclude TTL from the comparison key.
5. WHERE the IgnoreTTL input parameter is set to false, THE Sync_Lambda SHALL include TTL as part of the comparison key.

---

### Requirement 4: Diff Computation

**User Story:** As an application team member, I want only necessary DNS changes applied in Route 53, so that mirrored records match BIND without disruptive full-zone replacements.

#### Acceptance Criteria

1. WHEN normalization is complete, THE Sync_Lambda SHALL identify records present in the AXFR result but absent from Route53_Zone as CREATE operations.
2. WHEN normalization is complete, THE Sync_Lambda SHALL identify records present in both sources with differing resource data or TTL (when TTL comparison is enabled) as UPSERT operations.
3. WHEN normalization is complete, THE Sync_Lambda SHALL identify records present in Route53_Zone but absent from the AXFR result as DELETE operations.
4. THE Sync_Lambda SHALL limit the diff to the following record types: A, AAAA, CNAME, MX, TXT, SRV, and PTR.
5. THE Sync_Lambda SHALL exclude apex NS records from the diff because Route53_Zone manages those records.
6. THE Sync_Lambda SHALL exclude SOA records from the diff.
7. IF a CNAME record in the AXFR result conflicts with an existing record of a different type at the same name in Route53_Zone, THEN THE Sync_Lambda SHALL log a conflict warning and skip that record.
8. WHEN the diff produces zero operations, THE Sync_Lambda SHALL treat the run as successful without calling `ChangeResourceRecordSets`.

---

### Requirement 5: Change Application to Route 53

**User Story:** As a platform engineer, I want computed changes applied in batched Route 53 API calls, so that the private hosted zone reflects BIND state reliably and within API limits.

#### Acceptance Criteria

1. WHEN the diff produces one or more change operations, THE Sync_Lambda SHALL submit the changes using `ChangeResourceRecordSets` in batches of no more than 1000 changes per request.
2. WHEN all change batches are submitted successfully, THE Sync_Lambda SHALL log a summary containing the count of CREATE, UPSERT, and DELETE operations applied.
3. IF a `ChangeResourceRecordSets` API call fails, THEN THE Sync_Lambda SHALL log the error including the failed batch details and terminate the invocation with a non-zero exit status.
4. WHEN the diff produces zero change operations, THE Sync_Lambda SHALL log that the zone is already synchronized and terminate with a success status.
5. THE Sync_Lambda SHALL be idempotent: running twice against unchanged BIND and Route 53 state SHALL NOT produce additional changes on the second run.

---

### Requirement 6: Two-VPC Demo Topology

**User Story:** As a demo reviewer, I want separate on-prem and workload VPCs linked by Site-to-Site VPN, so that the demo mirrors how BIND authority and AWS workloads are connected in production.

#### Acceptance Criteria

1. THE demo stack SHALL provision OnPrem_VPC and Workload_VPC with non-overlapping CIDR blocks.
2. THE BIND_EC2 and VPN_Appliance SHALL reside in OnPrem_VPC only.
3. THE Virtual_Private_Gateway, Sync_Lambda, and Test_Instance SHALL reside in Workload_VPC only.
4. THE Route53_Zone SHALL be associated with Workload_VPC and SHALL NOT be associated with OnPrem_VPC.
5. THE demo stack SHALL NOT use VPC peering between OnPrem_VPC and Workload_VPC.
6. THE demo documentation SHALL label OnPrem_VPC as simulated on-premises and Workload_VPC as the AWS application network.

---

### Requirement 7: BIND Master on EC2 (OnPrem VPC)

**User Story:** As a demo reviewer, I want BIND on an EC2 instance in the on-prem VPC, so that I can edit zone files and see authoritative DNS behavior before mirroring to AWS.

#### Acceptance Criteria

1. THE BIND_EC2 SHALL run BIND named as authoritative master for the `corp.internal` zone.
2. THE BIND_EC2 SHALL use a private IP address in OnPrem_VPC as the AXFR target (`MasterDns`).
3. THE BIND_EC2 security group SHALL allow inbound TCP port 53 from the Sync_Lambda subnet CIDR in Workload_VPC (traffic routed via Site_to_Site_VPN).
4. THE BIND_EC2 SHALL NOT expose DNS (TCP/UDP 53) to `0.0.0.0/0`.
5. THE demo documentation SHALL describe how to SSH to BIND_EC2, edit the zone file, and reload BIND.

---

### Requirement 8: On-Prem Client Validation (Optional)

**User Story:** As a demo reviewer, I want an EC2 in the on-prem VPC that resolves directly from BIND, so that I can confirm the zone change on the authoritative server before waiting for Route 53 sync.

#### Acceptance Criteria

1. WHERE deployed, THE OnPrem_Instance SHALL query BIND_EC2 as its DNS resolver for `corp.internal` names.
2. WHEN a record is added or changed on BIND_EC2 and BIND is reloaded, THE OnPrem_Instance SHALL return the updated answer without waiting for Sync_Lambda or Route 53.
3. THE demo documentation SHALL explain that OnPrem_Instance proves BIND is authoritative; Test_Instance proves the mirror works in Workload_VPC.

---

### Requirement 9: BIND Access Control Configuration

**User Story:** As a security reviewer, I want BIND to allow zone transfer only from the Lambda subnet, so that internal zone data cannot be pulled by arbitrary hosts—even across the VPN.

#### Acceptance Criteria

1. THE BIND_Master SHALL configure the `allow-transfer` directive for the `corp.internal` zone to permit only the Sync_Lambda subnet CIDR in Workload_VPC.
2. IF an AXFR request originates from an IP address outside the allowed CIDR, THEN THE BIND_Master SHALL refuse the transfer.
3. THE demo documentation SHALL describe how to verify refused transfers from unauthorized sources.

---

### Requirement 10: Site-to-Site VPN Connectivity

**User Story:** As a platform engineer, I want AWS Site-to-Site VPN between the two VPCs, so that Sync_Lambda reaches BIND the way it would from a real AWS workload VPC connected to on-premises.

#### Acceptance Criteria

1. THE demo stack SHALL provision Site_to_Site_VPN with a Virtual_Private_Gateway on Workload_VPC and a Customer_Gateway backed by VPN_Appliance in OnPrem_VPC.
2. THE Site_to_Site_VPN SHALL establish at least one VPN_Tunnel in the `UP` state before sync validation begins.
3. THE Workload_VPC route tables SHALL route OnPrem_VPC CIDR traffic through the Virtual_Private_Gateway.
4. THE OnPrem_VPC route tables SHALL route Workload_VPC CIDR traffic through VPN_Appliance.
5. THE Workload_VPC SHALL contain at least one private subnet for Sync_Lambda ENI attachment.
6. THE Workload_VPC SHALL provide an outbound path from the Sync_Lambda subnet to the Route 53 API via NAT gateway or VPC interface endpoint (Route 53 API traffic does not traverse the VPN).
7. THE Sync_Lambda subnet SHALL reach BIND_EC2 on TCP port 53 over VPN_Tunnel; THE Test_Instance SHALL NOT require connectivity to BIND_EC2 for DNS validation (it uses AmazonProvidedDNS and Route53_Zone).
8. THE BIND_EC2 and Sync_Lambda subnets SHALL use security groups to restrict TCP port 53 access to the Lambda subnet CIDR only.
9. THE demo documentation SHALL describe how to verify VPN tunnel status and estimated cost (~$0.05/hr connection fee while provisioned).

---

### Requirement 11: IAM Permissions

**User Story:** As a security reviewer, I want Sync_Lambda granted only the permissions it needs, so that a compromised function cannot broadly alter AWS resources.

#### Acceptance Criteria

1. THE Sync_Lambda execution role SHALL include the `route53:ListResourceRecordSets` permission scoped to the target Route53_Zone ARN.
2. THE Sync_Lambda execution role SHALL include the `route53:ChangeResourceRecordSets` permission scoped to the target Route53_Zone ARN.
3. THE Sync_Lambda execution role SHALL include `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, and `ec2:DeleteNetworkInterface` permissions for VPC attachment.
4. THE Sync_Lambda execution role SHALL include `logs:CreateLogGroup`, `logs:CreateLogStream`, and `logs:PutLogEvents` permissions for CloudWatch Logs write access.
5. THE Sync_Lambda execution role SHALL NOT include permissions beyond those listed in criteria 1 through 4.

---

### Requirement 12: Scheduled Execution

**User Story:** As an operations owner, I want sync on a predictable schedule, so that BIND changes reach Workload_VPC DNS without someone running a script manually.

#### Acceptance Criteria

1. THE EventBridge_Schedule SHALL invoke Sync_Lambda at a configurable interval with a default of every 15 minutes.
2. WHEN EventBridge_Schedule triggers Sync_Lambda, THE EventBridge_Schedule SHALL pass a JSON payload containing Domain, MasterDns, ZoneId, and IgnoreTTL parameters.
3. THE EventBridge_Schedule SHALL support targeting the same Sync_Lambda with different JSON payloads for multiple zones via separate rules.
4. THE demo documentation SHALL state the default Sync_Interval and how Propagation_Delay relates to it for reviewers.

---

### Requirement 13: Lambda Input Validation

**User Story:** As a platform engineer, I want invalid configuration rejected before any network or API calls, so that misconfiguration is obvious in logs rather than mid-sync.

#### Acceptance Criteria

1. WHEN Sync_Lambda is invoked, THE Sync_Lambda SHALL validate that the Domain parameter is a non-empty string representing a valid DNS domain name.
2. WHEN Sync_Lambda is invoked, THE Sync_Lambda SHALL validate that the MasterDns parameter is a valid IPv4 or IPv6 address (BIND_EC2 private IP in OnPrem_VPC).
3. WHEN Sync_Lambda is invoked, THE Sync_Lambda SHALL validate that the ZoneId parameter is a non-empty string matching the Route 53 hosted zone ID format.
4. IF any input parameter fails validation, THEN THE Sync_Lambda SHALL log the validation error and terminate the invocation with a non-zero exit status without attempting zone transfer.

---

### Requirement 14: DNS Resolution Validation (Workload VPC)

**User Story:** As a demo reviewer, I want to query DNS from an EC2 in Workload_VPC after BIND changes, so that I can confirm mirrored records resolve via Route 53—not by talking to BIND directly.

#### Acceptance Criteria

1. WHEN Test_Instance in Workload_VPC queries a record that exists in Route53_Zone, THE AmazonProvidedDNS resolver SHALL return record data matching the BIND_Master zone file.
2. WHEN a record is changed on BIND_EC2 and one Sync_Interval has elapsed plus sync execution time, THE Test_Instance SHALL receive the updated record data from AmazonProvidedDNS.
3. WHEN a record is deleted from BIND_EC2 and one Sync_Interval has elapsed plus sync execution time, THE Test_Instance SHALL receive an NXDOMAIN or empty response for that record from AmazonProvidedDNS.
4. THE Test_Instance SHALL use the VPC default resolver (AmazonProvidedDNS at the VPC network base + 2); THE demo SHALL NOT configure Test_Instance to use BIND_EC2 as its resolver.
5. THE demo validation steps SHALL document the expected Propagation_Delay so reviewers do not interpret schedule lag as a failure.

---

### Requirement 15: Route 53 Private Hosted Zone Configuration

**User Story:** As an application team member, I want the private hosted zone associated with Workload_VPC only, so that instances there resolve `corp.internal` from the mirror without custom resolver configuration.

#### Acceptance Criteria

1. THE Route53_Zone SHALL be configured as a private hosted zone for the `corp.internal` domain.
2. THE Route53_Zone SHALL be associated with Workload_VPC.
3. THE Route53_Zone SHALL NOT be associated with OnPrem_VPC.
4. THE Route53_Zone SHALL NOT be delegated publicly.

---

### Requirement 16: Observability and Logging

**User Story:** As an operations owner, I want structured sync logs, so that I can answer “did it run?”, “what changed?”, and “what was skipped?” without reading BIND and Route 53 side by side.

#### Acceptance Criteria

1. WHEN Sync_Lambda begins execution, THE Sync_Lambda SHALL log the invocation start with the input parameters (Domain, MasterDns, ZoneId, IgnoreTTL).
2. WHEN Sync_Lambda completes successfully, THE Sync_Lambda SHALL log the total execution duration and the number of records processed from AXFR.
3. WHEN Sync_Lambda applies changes, THE Sync_Lambda SHALL log the count of CREATE, UPSERT, and DELETE operations per batch.
4. IF Sync_Lambda encounters a recoverable warning (malformed record, CNAME conflict), THEN THE Sync_Lambda SHALL log the warning with the affected record name and type.
5. WHEN Sync_Lambda fails, THE Sync_Lambda SHALL log a clear failure reason sufficient for an operator to distinguish VPN/tunnel, routing, AXFR, validation, and Route 53 API errors.

---

### Requirement 17: Failure and Degraded Behavior

**User Story:** As an operations owner, I want predictable behavior when BIND, VPN, or sync is unavailable, so that I know what Workload_VPC applications will still experience.

#### Acceptance Criteria

1. IF Sync_Lambda cannot complete AXFR, THEN Route53_Zone SHALL retain its last successfully synchronized records; THE Sync_Lambda SHALL NOT delete Route 53 records solely because AXFR failed.
2. IF a scheduled sync run fails, THEN THE next scheduled invocation SHALL attempt sync again without manual intervention.
3. IF the VPN_Tunnel is down, THEN Sync_Lambda AXFR SHALL fail and THE demo documentation SHALL explain that Route 53 continues serving the last synced state.
4. THE demo documentation SHALL explain that stale Route 53 data may be served in Workload_VPC until a successful sync occurs after BIND changes.
5. THE demo documentation SHALL describe how to inspect CloudWatch Logs, VPN tunnel status, and EventBridge invocation history to confirm sync health.

---

### Requirement 18: Demo Documentation and Review Experience

**User Story:** As a demo reviewer or learner, I want a concise walkthrough of the two-VPC + VPN architecture and validation steps, so that I can reproduce the full hybrid story without reading source code first.

#### Acceptance Criteria

1. THE project documentation SHALL include an architecture diagram or overview showing OnPrem_VPC (BIND_EC2, VPN_Appliance, optional OnPrem_Instance), Workload_VPC (Virtual_Private_Gateway, Sync_Lambda, Test_Instance, Route53_Zone), and Site_to_Site_VPN tunnels.
2. THE project documentation SHALL list prerequisites (AWS account, SSH path to BIND_EC2, VPN tunnel verification) in plain language.
3. THE project documentation SHALL provide step-by-step validation:
   - Confirm VPN tunnel is `UP`.
   - Edit a record on BIND_EC2; confirm on OnPrem_Instance (if deployed) resolves immediately from BIND.
   - Wait for Sync_Interval; query the same name from Test_Instance in Workload_VPC; confirm answer matches BIND.
4. THE project documentation SHALL note that production replaces OnPrem_VPC with a real datacenter using the same Site-to-Site VPN pattern (Direct Connect is an alternative for higher throughput).
5. THE project documentation SHALL include estimated lab cost for VPN (~$1.20/day connection fee) and recommend stack teardown when idle.
6. THE project documentation SHALL call out Non-Goals and production gaps (HA, redundant tunnels, IXFR, change approval, rollback).

---

## Success Metrics

The demo meets its intent when a reviewer can confirm all of the following:

| Metric | Target |
|--------|--------|
| **Hybrid topology** | BIND + VPN appliance in OnPrem_VPC; VGW + Route 53 + Test_Instance in Workload_VPC; Site-to-Site VPN (not peering) links them. |
| **VPN health** | At least one tunnel `UP`; Sync_Lambda reaches BIND_EC2 private IP over the tunnel. |
| **Authoritative BIND** | OnPrem_Instance (or direct query to BIND_EC2) returns new records immediately after BIND reload. |
| **Mirror correctness** | After BIND change + one Sync_Interval, Test_Instance in Workload_VPC resolves the same data via AmazonProvidedDNS. |
| **Isolation of resolution paths** | Test_Instance does not use BIND as resolver; it proves Route 53 mirroring, not DNS forwarding over VPN. |
| **Idempotency** | Back-to-back syncs with no BIND changes produce zero Route 53 changes. |
| **Security posture** | No public BIND exposure; AXFR refused from non-Lambda CIDR; zone not public. |
| **Teachability** | A new reader understands the hybrid two-VPC + VPN story and validation steps in under 30 minutes using documentation alone. |

---

## Open Questions (for future spec iterations)

- Should OnPrem_Instance be required or optional in the default demo stack?
- Should the demo include a manual “sync now” trigger (console test invoke) in addition to the schedule?
- Is IgnoreTTL default `true` or `false` for the demo stack?
- Should the VPN appliance and BIND share one EC2 or run on separate instances?
- Should alarm thresholds (failed invocations, tunnel down, zero records from AXFR) be in scope for a follow-on operational requirements doc?
