# Deployment Guide

## Prerequisites

- **Two AWS accounts** (simulated on-prem + workload)
- **AWS CLI profiles** (defaults used by Terraform):
  - `bind-demo-onprem` — on-prem account
  - `bind-demo-workload` — workload account
- Terraform ≥ 1.5
- Python 3.14 (local tests)
- Default region: **`ap-southeast-2`** (Sydney)
- [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) for the AWS CLI (all EC2 access is via SSM; no SSH keys).

## Deploy

Each account gets its own VPC. No VPC IDs to supply. Deploy order is automated:

1. On-prem account — VPC, BIND, VPN appliance (+ EIP)
2. Workload account — VPC, VGW, Site-to-Site VPN, Lambda, Route 53
3. On-prem account — configure VPN appliance IPsec from workload tunnel outputs

```bash
./scripts/deploy_stacks.sh
```

Or step manually:

```bash
./scripts/build_lambda.sh
terraform -chdir=infra/terraform/onprem init && terraform -chdir=infra/terraform/onprem apply
terraform -chdir=infra/terraform/workload init && terraform -chdir=infra/terraform/workload apply
terraform -chdir=infra/terraform/onprem apply
```

Step 3 reads VPN tunnel outputs from `infra/terraform/workload/terraform.tfstate` automatically.

**Avoid drift:** always apply workload before the final on-prem apply. Do not run on-prem apply alone before the workload stack exists.

Note outputs (workload stack unless noted):

- `bind_private_ip` — BIND master IP in on-prem account (`MasterDns`)
- `route53_zone_id`
- `sync_lambda_name`
- `test_instance_public_ip`

On-prem stack: `bind_instance_id`, `vpn_appliance_public_ip`

## Manual sync now

```bash
aws --profile bind-demo-workload lambda invoke \
  --function-name "$(terraform -chdir=infra/terraform/workload output -raw sync_lambda_name)" \
  --payload '{"Domain":"corp.internal","MasterDns":"'"$(terraform -chdir=infra/terraform/workload output -raw bind_private_ip)"'","ZoneId":"'"$(terraform -chdir=infra/terraform/workload output -raw route53_zone_id)"'","IgnoreTTL":true}' \
  /tmp/sync-out.json && cat /tmp/sync-out.json
```

## Validation workflow

1. **VPN** — `aws --profile bind-demo-workload ec2 describe-vpn-connections --vpn-connection-ids "$(terraform -chdir=infra/terraform/workload output -raw vpn_connection_id)"` — tunnel `UP`.
2. **BIND** — SSM to BIND; edit zone; `sudo rndc reload`.
3. **OnPrem (optional)** — If `OnPrem_Instance` is deployed, verify immediate answer: `dig @<bind_private_ip> app.corp.internal A +short` from the instance. Proves BIND authority before sync.
4. **Sync** — manual invoke or wait 15 minutes (Sync_Interval + Lambda runtime).
5. **Resolve** — on Test_Instance: `dig app.corp.internal` (uses AmazonProvidedDNS via Route 53 mirror).

## Connect to EC2 (Session Manager)

All instances use **SSM Session Manager** (no SSH keys). Allow 1–2 minutes after launch for instances to show as **Online** in Systems Manager.

| Instance | Profile | Command |
| --- | --- | --- |
| BIND | `bind-demo-onprem` | `aws --profile bind-demo-onprem ssm start-session --target "$(terraform -chdir=infra/terraform/onprem output -raw bind_instance_id)"` |
| VPN appliance | `bind-demo-onprem` | `aws --profile bind-demo-onprem ssm start-session --target "$(terraform -chdir=infra/terraform/onprem output -raw vpn_appliance_instance_id)"` |
| OnPrem test (optional) | `bind-demo-onprem` | `aws --profile bind-demo-onprem ssm start-session --target "$(terraform -chdir=infra/terraform/onprem output -raw onprem_instance_id)"` |
| Test instance | `bind-demo-workload` | `aws --profile bind-demo-workload ssm start-session --target "$(terraform -chdir=infra/terraform/workload output -raw test_instance_id)"` |

On-prem private subnets use **SSM VPC interface endpoints** (`ssm`, `ec2messages`, `ssmmessages`). The workload test instance reaches SSM via the NAT gateway.

## BIND validation commands

### Edit zone files on BIND_EC2

Connect via Session Manager:

```bash
aws --profile bind-demo-onprem ssm start-session --target "$(terraform -chdir=infra/terraform/onprem output -raw bind_instance_id)"
```

Once connected, edit the zone file:

```bash
sudo vim /var/named/corp.internal.zone
```

Example: add an A record:

```dns
app    IN  A  10.0.1.50
```

After editing, update the SOA serial (convention: `YYYYMMDDNN`), then reload.

### Reload BIND after zone changes

```bash
sudo rndc reload
```

Confirm the reload succeeded:

```bash
sudo rndc status
# Look for: "server is up and running"

# Check BIND logs for reload confirmation
sudo journalctl -u named --since "1 min ago" --no-pager
```

### Verify AXFR works from the Lambda subnet

From any host in the Lambda subnet (10.1.1.0/24), run a full zone transfer to confirm BIND allows it:

```bash
dig @<bind_private_ip> corp.internal AXFR
```

Expected output: full zone listing with all records, ending with a repeated SOA record.

If running from Test_Instance (which is in a different subnet), this should be **refused** — only the Lambda subnet CIDR is in `allow-transfer`.

### Verify AXFR is refused from unauthorized sources

From Test_Instance or any host outside the Lambda subnet CIDR (10.1.1.0/24):

```bash
dig @<bind_private_ip> corp.internal AXFR
```

Expected output:

```text
; Transfer failed.
```

Or in BIND logs on BIND_EC2:

```bash
sudo journalctl -u named --since "5 min ago" | grep "denied"
# Expected: "transfer of 'corp.internal/IN': AXFR denied"
```

This confirms the `allow-transfer { 10.1.1.0/24; };` directive is working correctly. Only Sync_Lambda (running in that subnet) can pull the zone.

### Verify immediate resolution from OnPrem_Instance (Req 8)

OnPrem_Instance is optional in the demo stack. If deployed, it resolves directly from BIND_EC2—proving the authoritative server has the record **before** any Route 53 sync occurs.

**Check if OnPrem_Instance is deployed:**

```bash
terraform -chdir=infra/terraform/onprem output onprem_instance_id 2>/dev/null && echo "Deployed" || echo "Not deployed"
```

**Connect to OnPrem_Instance** via Session Manager:

```bash
aws --profile bind-demo-onprem ssm start-session --target "$(terraform -chdir=infra/terraform/onprem output -raw onprem_instance_id)"
```

**Verify immediate answer after BIND reload** — this should return the new record instantly (no sync wait needed):

```bash
dig @<bind_private_ip> app.corp.internal A +short
# Expected: 10.0.1.50 (or whatever you added to the zone)
```

If the record was just added/changed on BIND_EC2 and `rndc reload` was run, OnPrem_Instance must return the updated answer immediately. This confirms BIND is authoritative and the zone reload succeeded. Test_Instance (in Workload_VPC) will NOT have the record yet—it only resolves from Route 53 after a sync cycle.

### Basic dig commands for testing resolution

**Query BIND directly** (from OnPrem_Instance or BIND_EC2 itself):

```bash
# A record lookup
dig @<bind_private_ip> app.corp.internal A +short

# Any record type
dig @<bind_private_ip> mail.corp.internal MX +short

# Full response with headers
dig @<bind_private_ip> app.corp.internal A
```

**Query Route 53 mirror** (SSM to Test_Instance in workload account):

```bash
aws --profile bind-demo-workload ssm start-session --target "$(terraform -chdir=infra/terraform/workload output -raw test_instance_id)"
# then on the instance:
dig app.corp.internal A +short

# Verify the resolver being used
dig app.corp.internal A +short @169.254.169.253
```

**Compare BIND vs Route 53** to confirm sync:

```bash
# On BIND_EC2 or OnPrem_Instance
dig @<bind_private_ip> app.corp.internal A +short

# On Test_Instance (Route 53 mirror)
dig app.corp.internal A +short
```

Both should return the same answer after a successful sync cycle.

**Check for NXDOMAIN** (record deleted from BIND and synced):

```bash
dig app.corp.internal A +short
# Expected: empty response (NXDOMAIN) after sync completes
```

---

## Smoke Tests

Run these checks after deploying the stack to confirm the Lambda subnet has working connectivity to BIND (AXFR over VPN) and Route 53 (API access).

### Verify AXFR works from Lambda subnet

Invoke the sync Lambda manually and check CloudWatch Logs for a successful zone transfer:

```bash
aws --profile bind-demo-workload lambda invoke \
  --function-name "$(terraform -chdir=infra/terraform/workload output -raw sync_lambda_name)" \
  --payload '{"Domain":"corp.internal","MasterDns":"'"$(terraform -chdir=infra/terraform/workload output -raw bind_private_ip)"'","ZoneId":"'"$(terraform -chdir=infra/terraform/workload output -raw route53_zone_id)"'","IgnoreTTL":true}' \
  /tmp/sync-out.json && cat /tmp/sync-out.json
```

**Pass criteria:** The response shows `"status": "success"` and CloudWatch Logs contain an `axfr_complete` event with a non-zero record count.

```bash
# Check logs for the AXFR result
aws --profile bind-demo-workload logs filter-log-events \
  --log-group-name "/aws/lambda/$(terraform -chdir=infra/terraform/workload output -raw sync_lambda_name)" \
  --filter-pattern "axfr_complete" \
  --limit 5
```

If the invoke fails with an AXFR error, check VPN tunnel status and BIND security group rules (see [Runbook — AXFR refused](RUNBOOK.md#axfr-refused)).

### Verify Route 53 API access works from Lambda subnet

A successful sync (above) confirms Route 53 API access — the Lambda must call both `ListResourceRecordSets` and `ChangeResourceRecordSets` during a normal run.

If Route 53 access is broken, the sync will fail with a `r53_read` or `r53_write` stage error:

```bash
# Check for Route 53 API errors
aws --profile bind-demo-workload logs filter-log-events \
  --log-group-name "/aws/lambda/$(terraform -chdir=infra/terraform/workload output -raw sync_lambda_name)" \
  --filter-pattern "r53_read r53_write" \
  --limit 5
```

**Pass criteria:** No `r53_read` or `r53_write` errors in recent logs, and at least one sync completed with `sync_success`.

If Route 53 API calls fail, verify:

- Lambda security group allows egress on port 443 via NAT gateway to Route 53 API
- IAM execution role has `route53:ListResourceRecordSets` and `route53:ChangeResourceRecordSets` scoped to the zone ARN

---

## Verify CloudWatch structured logs (Req 16)

After a successful sync run, confirm that CloudWatch Logs contain the expected structured JSON events. Each log line is a single JSON object with an `event` field.

### Expected log events per sync invocation

| Event | Fields | Meaning |
|-------|--------|---------|
| `sync_start` | `domain`, `master_dns`, `zone_id`, `ignore_ttl` | Lambda began execution with these input parameters |
| `axfr_complete` | `record_count`, `duration_ms` | Zone transfer finished; shows record count and AXFR duration |
| `diff_summary` | `creates`, `upserts`, `deletes`, `conflicts` | Computed diff breakdown before applying changes |
| `apply_batch` | `batch_index`, `creates`, `upserts`, `deletes` | One batch of Route 53 changes submitted (only if diff is non-empty) |
| `sync_success` | `total_duration_ms`, `axfr_count` | Sync completed successfully with total duration |
| `zone_synchronized` | `message` | Diff was empty — zone already in sync (replaces `apply_batch`) |

### Warning and error events

| Event | Fields | Meaning |
|-------|--------|---------|
| `sync_warning` | `message`, `record_name`, `record_type` | Recoverable issue (malformed record, CNAME conflict) — record was skipped |
| `sync_error` | `stage`, `error` | Fatal failure; `stage` identifies where: `validation`, `vpn`, `axfr`, `r53_read`, or `r53_write` |

### CLI commands to verify

**View recent sync events:**

```bash
aws --profile bind-demo-workload logs filter-log-events \
  --log-group-name "/aws/lambda/$(terraform -chdir=infra/terraform/workload output -raw sync_lambda_name)" \
  --filter-pattern "sync_start" \
  --limit 5
```

**Confirm a complete lifecycle (start → success):**

```bash
# Get the latest log stream
LATEST_STREAM=$(aws logs describe-log-streams \
  --log-group-name "/aws/lambda/$(terraform -chdir=infra/terraform/workload output -raw sync_lambda_name)" \
  --order-by LastEventTime --descending --limit 1 \
  --query 'logStreams[0].logStreamName' --output text)

# Read all events from that stream
aws logs get-log-events \
  --log-group-name "/aws/lambda/$(terraform -chdir=infra/terraform/workload output -raw sync_lambda_name)" \
  --log-stream-name "$LATEST_STREAM" \
  --query 'events[].message' --output text
```

Expected output for a sync with changes:

```json
{"event": "sync_start", "domain": "corp.internal", "master_dns": "10.0.1.10", "zone_id": "Z...", "ignore_ttl": true}
{"event": "axfr_complete", "record_count": 5, "duration_ms": 230}
{"event": "diff_summary", "creates": 1, "upserts": 0, "deletes": 0, "conflicts": 0}
{"event": "apply_batch", "batch_index": 0, "creates": 1, "upserts": 0, "deletes": 0}
{"event": "sync_success", "total_duration_ms": 1450, "axfr_count": 5}
```

**Check for warnings (malformed records, CNAME conflicts):**

```bash
aws --profile bind-demo-workload logs filter-log-events \
  --log-group-name "/aws/lambda/$(terraform -chdir=infra/terraform/workload output -raw sync_lambda_name)" \
  --filter-pattern "sync_warning" \
  --limit 10
```

**Check for errors and identify failure stage:**

```bash
aws --profile bind-demo-workload logs filter-log-events \
  --log-group-name "/aws/lambda/$(terraform -chdir=infra/terraform/workload output -raw sync_lambda_name)" \
  --filter-pattern "sync_error" \
  --limit 10
```

The `stage` field in error events maps directly to the pipeline step that failed:

- `validation` — bad input parameters (Domain, MasterDns, ZoneId)
- `axfr` — zone transfer failure (timeout, connection refused, VPN down)
- `r53_read` — `ListResourceRecordSets` API error
- `r53_write` — `ChangeResourceRecordSets` API error

### Pass criteria

A healthy sync invocation MUST produce:

1. Exactly one `sync_start` event (confirms Lambda began)
2. Exactly one `axfr_complete` event with `record_count > 0`
3. Exactly one `diff_summary` event (shows batch counts)
4. Zero or more `apply_batch` events (one per batch, only if changes exist)
5. Exactly one `sync_success` event with `total_duration_ms > 0`
6. Zero `sync_error` events

---

## Propagation delay

Expect up to **Sync_Interval (15 min)** plus Lambda runtime after a BIND change.

## Teardown

Tear down the stack when you are not actively using it to avoid unnecessary charges.

```bash
./scripts/destroy_stacks.sh
```

VPN charges stop when the VPN connection is deleted (~$0.05/hr, ~$1.20/day while provisioned). Recommend destroying the stack when idle to minimize costs.
