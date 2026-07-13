import json
import logging
import sys
from typing import Any

from zone_sync.models import ApplyResult, DiffResult, ValidatedInput

logger = logging.getLogger("zone_sync")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def _emit(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, default=str))


def log_start(params: ValidatedInput) -> None:
    _emit(
        "sync_start",
        domain=params.domain,
        master_dns=params.master_dns,
        zone_id=params.zone_id,
        ignore_ttl=params.ignore_ttl,
    )


def log_axfr_result(record_count: int, duration_ms: int) -> None:
    _emit("axfr_complete", record_count=record_count, duration_ms=duration_ms)


def log_diff_summary(diff: DiffResult) -> None:
    _emit(
        "diff_summary",
        creates=len(diff.creates),
        upserts=len(diff.upserts),
        deletes=len(diff.deletes),
        conflicts=len(diff.conflicts),
    )


def log_apply_batch(
    batch_index: int, creates: int, upserts: int, deletes: int
) -> None:
    _emit(
        "apply_batch",
        batch_index=batch_index,
        creates=creates,
        upserts=upserts,
        deletes=deletes,
    )


def log_success(total_duration_ms: int, axfr_count: int) -> None:
    _emit("sync_success", total_duration_ms=total_duration_ms, axfr_count=axfr_count)


def log_synchronized() -> None:
    _emit("zone_synchronized", message="Zone already synchronized")


def log_warning(message: str, record_name: str, record_type: str) -> None:
    _emit(
        "sync_warning",
        message=message,
        record_name=record_name,
        record_type=record_type,
    )


def log_error(stage: str, error: Exception) -> None:
    _emit("sync_error", stage=stage, error=str(error))
