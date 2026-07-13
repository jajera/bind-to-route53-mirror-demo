"""Unit tests for zone_sync.axfr_client — mocked dnspython."""

from unittest.mock import MagicMock, patch

import dns.name
import dns.rdatatype
import pytest

from zone_sync.axfr_client import fetch_zone
from zone_sync.exceptions import AXFRError


@patch("dns.zone.from_xfr")
@patch("dns.query.xfr")
def test_fetch_zone_success(mock_xfr, mock_from_xfr):
    """Successful AXFR returns parsed RawRecords."""
    zone_name = dns.name.from_text("corp.internal.")

    # Build a mock zone with one A record node
    mock_rdata = MagicMock()
    mock_rdata.to_text.return_value = "10.0.0.1"

    mock_rdataset = MagicMock()
    mock_rdataset.rdtype = dns.rdatatype.RdataType.A
    mock_rdataset.ttl = 300
    mock_rdataset.__iter__ = lambda self: iter([mock_rdata])

    mock_node = MagicMock()
    mock_node.rdatasets = [mock_rdataset]

    rel_name = dns.name.from_text("app", origin=None)

    mock_zone = MagicMock()
    mock_zone.nodes = {rel_name: mock_node}
    mock_from_xfr.return_value = mock_zone

    records = fetch_zone("10.0.1.10", "corp.internal", timeout=10)

    assert len(records) == 1
    assert records[0].name == "app.corp.internal."
    assert records[0].rtype == "A"
    assert records[0].ttl == 300
    assert records[0].rdata == ["10.0.0.1"]
    mock_xfr.assert_called_once()


@patch("dns.zone.from_xfr")
@patch("dns.query.xfr")
def test_fetch_zone_timeout(mock_xfr, mock_from_xfr):
    """AXFR timeout raises AXFRError."""
    mock_from_xfr.side_effect = Exception("Transfer timed out")

    with pytest.raises(AXFRError, match="AXFR failed"):
        fetch_zone("10.0.1.10", "corp.internal", timeout=5)


@patch("dns.zone.from_xfr")
@patch("dns.query.xfr")
def test_fetch_zone_refused(mock_xfr, mock_from_xfr):
    """Refused transfer raises AXFRError."""
    mock_from_xfr.side_effect = Exception("Transfer refused")

    with pytest.raises(AXFRError, match="AXFR failed"):
        fetch_zone("10.0.1.10", "corp.internal")
