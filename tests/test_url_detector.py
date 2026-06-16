import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service_link_scanner"))

from url_scan.url_detector import URLDetector  # noqa: E402


def test_heuristic_punycode():
    d = URLDetector()
    ok, reason = d.heuristic_check("https://xn--abc.example.com/foo")
    assert ok is True
    assert "xn--" in reason or "Punycode" in reason


def test_heuristic_suspicious_tld():
    d = URLDetector()
    ok, reason = d.heuristic_check("https://phish.example.xyz/path")
    assert ok is True
    assert ".xyz" in reason


def test_heuristic_safe():
    d = URLDetector()
    ok, _ = d.heuristic_check("https://www.google.com/")
    assert ok is False


def test_row_from_scan_includes_hop_count_safe():
    d = URLDetector()
    row = d._row_from_scan("https://a.com", "https://a.com", 2, set(), set())
    assert row["label"] == "Safe"
    assert row["hop_count"] == 2


def test_row_from_scan_many_hops_flagged_suspicious():
    d = URLDetector()
    row = d._row_from_scan("https://a.com", "https://final.com", 5, set(), set())
    assert row["label"] == "Suspicious"
    assert row["hop_count"] == 5


def test_analyze_batch_light_mode_skips_redirect_fetches():
    """輕量模式：不逐一追蹤 redirect（省去每條 URL 的 server 端 GET）。"""
    d = URLDetector()
    d.check_google_safe_browsing_batch = AsyncMock(return_value=set())
    d.get_final_url = AsyncMock()  # 輕量模式不應呼叫

    rows = asyncio.run(d.analyze_batch(["https://example.com/path"], follow_redirects=False))

    d.get_final_url.assert_not_called()
    assert rows[0]["final_url"] == "https://example.com/path"
    assert rows[0]["hop_count"] == 0
    assert rows[0]["label"] == "Safe"
