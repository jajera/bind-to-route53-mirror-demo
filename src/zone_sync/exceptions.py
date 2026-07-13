class SyncError(Exception):
    """Base error for sync pipeline."""


class ValidationError(SyncError):
    """Invalid Lambda event input."""


class AXFRError(SyncError):
    """Zone transfer failed."""


class Route53ReadError(SyncError):
    """Route 53 read failed."""


class ApplyError(SyncError):
    """Route 53 change application failed."""
