import re
from urllib.parse import urlparse

_PRIVATE_PATTERNS = [
    r"^https?://localhost",
    r"^https?://127\.",
    r"^https?://192\.168\.",
    r"^https?://10\.",
    r"^https?://172\.(1[6-9]|2[0-9]|3[0-1])\.",
    r"^https?://169\.254\.",
    r"^https?://\[",  # IPv6 loopback
]

MAX_URL_LENGTH = 2048


def assert_public_http_url(url: str) -> None:
    """
    確保 URL 符合以下條件，否則拋出 ValueError：
    - scheme 為 http 或 https
    - 長度不超過 MAX_URL_LENGTH
    - 不指向私有 / 迴環網路（SSRF 防護）
    """
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"URL 長度不得超過 {MAX_URL_LENGTH} 字元")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"僅允許 http/https URL：{url}")

    for pattern in _PRIVATE_PATTERNS:
        if re.match(pattern, url.strip()):
            raise ValueError("不允許私有網路 URL")
