from detectors.url_detector import URLDetector


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
