# Runbook

## VPN tunnel down

**Symptoms:** Lambda logs `sync_error` stage `axfr`; AXFR timeout/refused.

**Checks:**

```bash
aws ec2 describe-vpn-connections --query 'VpnConnections[].VgwTelemetry'
```

**Impact:** Route 53 keeps last synced records; Workload_VPC serves stale DNS until sync succeeds.

**Actions:**

1. Verify VPN appliance EC2 is running.
2. On appliance: `sudo ipsec status`
3. Confirm routes: Workload VPC → OnPrem CIDR via VGW; OnPrem bind subnet → Workload CIDR via appliance ENI.

## AXFR refused

**Symptoms:** AXFR error; BIND logs transfer denied.

**Checks:**

- Lambda source IP is in `allow-transfer` CIDR (`10.1.1.0/24`).
- BIND security group allows TCP 53 from Lambda subnet.

**Test from Lambda subnet:** use manual invoke after fixing ACLs.

See also: [DEPLOYMENT.md — Verify AXFR is refused from unauthorized sources](DEPLOYMENT.md#verify-axfr-is-refused-from-unauthorized-sources) for validation commands.

## Route 53 API errors

**Symptoms:** `sync_error` stage `r53_read` or `r53_write`.

**Checks:**

- Lambda security group egress to Route 53 on 443 via NAT gateway.
- IAM policy scoped to hosted zone ARN.

## Degraded behavior — stale data in Workload_VPC

When any sync failure occurs (VPN down, AXFR refused, Route 53 API error, or Lambda timeout), Route 53 retains the last successfully synchronized records. Workload_VPC instances querying AmazonProvidedDNS will continue to receive answers based on that stale snapshot until a successful sync completes after BIND is updated.

This means:

- Records added on BIND after the last good sync will not resolve in Workload_VPC.
- Records deleted on BIND will continue to resolve in Workload_VPC with old data.
- Records modified on BIND will return the previous values.

The next scheduled EventBridge invocation will retry automatically — no manual intervention is needed unless the underlying issue (VPN, ACLs, IAM) persists.

## Confirming sync health

Use these three checks together to verify the sync pipeline is operating normally.

### CloudWatch Logs

Log group: `/aws/lambda/<project_name>-sync`

```bash
# Recent successful syncs
aws logs filter-log-events \
  --log-group-name "/aws/lambda/<project_name>-sync" \
  --filter-pattern "sync_success" \
  --limit 5

# Recent errors
aws logs filter-log-events \
  --log-group-name "/aws/lambda/<project_name>-sync" \
  --filter-pattern "sync_error" \
  --limit 5
```

Structured JSON events: `sync_start`, `axfr_complete`, `diff_summary`, `apply_batch`, `sync_success`, `sync_error`.

### VPN tunnel status

```bash
aws ec2 describe-vpn-connections --query 'VpnConnections[].VgwTelemetry'
```

At least one tunnel should show `Status: UP`. If both are `DOWN`, AXFR will fail.

### EventBridge invocation history

```bash
# List recent rule invocations (last 1 hour)
aws events list-rule-names-by-target \
  --target-arn "arn:aws:lambda:<region>:<account>:function:<project_name>-sync"

# Check EventBridge rule state
aws events describe-rule --name "<sync-schedule-rule-name>"

# View Lambda invocation metrics (invocations + errors over last hour)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=<project_name>-sync \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 900 \
  --statistics Sum

aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=<project_name>-sync \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 900 \
  --statistics Sum
```

A healthy pipeline shows: regular invocations every 15 minutes, zero errors, and `sync_success` events in CloudWatch Logs.

## Common failures

| Stage | Likely cause |
| --- | --- |
| validation | Bad EventBridge payload |
| axfr | VPN down, BIND down, ACL/SG block |
| r53_read | IAM or NAT path to Route 53 API |
| r53_write | Invalid change batch, throttling |
