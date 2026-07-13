import time
from typing import Any

from zone_sync import sync_logger as log
from zone_sync.applicator import apply_changes
from zone_sync.axfr_client import fetch_zone
from zone_sync.diff_engine import compute_diff
from zone_sync.exceptions import (
    ApplyError,
    AXFRError,
    Route53ReadError,
    ValidationError,
)
from zone_sync.normalizer import normalize_records
from zone_sync.route53_reader import fetch_route53_records
from zone_sync.validator import validate_event


def lambda_handler(event: dict, context: Any) -> dict:
    started = time.monotonic()
    try:
        params = validate_event(event)
    except ValidationError as exc:
        log.log_error("validation", exc)
        raise

    log.log_start(params)

    try:
        axfr_started = time.monotonic()
        raw_axfr = fetch_zone(params.master_dns, params.domain)
        axfr_ms = int((time.monotonic() - axfr_started) * 1000)
        log.log_axfr_result(len(raw_axfr), axfr_ms)
    except AXFRError as exc:
        log.log_error("axfr", exc)
        raise

    try:
        raw_r53 = fetch_route53_records(params.zone_id)
    except Route53ReadError as exc:
        log.log_error("r53_read", exc)
        raise

    zone_apex = f"{params.domain}."
    source, source_warnings = normalize_records(
        raw_axfr, params.ignore_ttl, zone_origin=params.domain
    )
    target, target_warnings = normalize_records(
        raw_r53, params.ignore_ttl, zone_origin=params.domain
    )
    for warning in source_warnings + target_warnings:
        log.log_warning(warning.message, warning.name, warning.rtype)

    diff = compute_diff(source, target, zone_apex, params.ignore_ttl)
    for name, source_type, target_type in diff.conflicts:
        log.log_warning(
            "CNAME conflict skipped",
            name,
            f"{source_type} vs {target_type}",
        )
    log.log_diff_summary(diff)

    if diff.is_empty:
        log.log_synchronized()
        return _success_response(0, 0, 0, started, len(raw_axfr), "Zone synchronized")

    try:
        apply_result = apply_changes(params.zone_id, diff, target=target)
        log.log_apply_batch(
            0,
            apply_result.creates_applied,
            apply_result.upserts_applied,
            apply_result.deletes_applied,
        )
    except ApplyError as exc:
        log.log_error("r53_write", exc)
        raise

    total_ms = int((time.monotonic() - started) * 1000)
    log.log_success(total_ms, len(raw_axfr))
    return _success_response(
        apply_result.creates_applied,
        apply_result.upserts_applied,
        apply_result.deletes_applied,
        started,
        len(raw_axfr),
        "Sync completed",
    )


def _success_response(
    creates: int,
    upserts: int,
    deletes: int,
    started: float,
    axfr_count: int,
    message: str,
) -> dict:
    return {
        "status": "success",
        "creates": creates,
        "upserts": upserts,
        "deletes": deletes,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "axfr_count": axfr_count,
        "message": message,
    }


