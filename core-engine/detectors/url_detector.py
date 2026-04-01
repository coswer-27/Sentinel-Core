import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

import httpx

from .base import BaseDetector

SUSPICIOUS_TLDS = {".top", ".xyz", ".tk", ".pw", ".gq", ".cf", ".ml"}
MAX_REDIRECTS = 5
GSB_MAX_URLS_PER_REQUEST = 500

GSB_CLIENT_ID = "senti-guard"
GSB_CLIENT_VERSION = "1.0.0"


def _normalize_url_for_compare(u: str) -> str:
    """與 GSB 回傳的 threat URL 比對時略為寬鬆（大小寫、尾端 /）。"""
    try:
        p = urlsplit(u.strip())
        path = p.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        netloc = p.netloc.lower()
        return urlunsplit((p.scheme.lower(), netloc, path, p.query, ""))
    except Exception:
        return u.strip()


class URLDetector(BaseDetector):
    async def get_final_url(self, url: str) -> tuple[str, int]:
        """
        追蹤 redirect，回傳 (final_url, hop_count)
        超時或失敗時回傳原始 url，hop_count = -1
        """
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                follow_redirects=True,
                max_redirects=MAX_REDIRECTS,
            ) as client:
                response = await client.get(url, follow_redirects=True)
                hops = len(response.history)
                final_url = str(response.url)
                return final_url, hops
        except Exception:
            return url, -1

    def _gsb_payload(self, threat_urls: list[str]) -> dict:
        return {
            "client": {
                "clientId": GSB_CLIENT_ID,
                "clientVersion": GSB_CLIENT_VERSION,
            },
            "threatInfo": {
                "threatTypes": [
                    "MALWARE",
                    "SOCIAL_ENGINEERING",
                    "UNWANTED_SOFTWARE",
                    "POTENTIALLY_HARMFUL_APPLICATION",
                ],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": u} for u in threat_urls],
            },
        }

    async def check_google_safe_browsing_batch(self, urls: list[str]) -> set[str]:
        """
        批次查詢 GSB v4 threatMatches:find（單次最多 500 個 URL）。
        回傳「命中」的 threat URL 集合（依 API 回傳字串；另做正規化供比對）。
        無 API Key 或失敗時回傳空集合（不拋錯）。
        """
        key = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")
        if not key or not urls:
            return set()

        malicious_raw: set[str] = set()

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                for i in range(0, len(urls), GSB_MAX_URLS_PER_REQUEST):
                    chunk = urls[i : i + GSB_MAX_URLS_PER_REQUEST]
                    body = self._gsb_payload(chunk)
                    resp = await client.post(
                        "https://safebrowsing.googleapis.com/v4/threatMatches:find",
                        params={"key": key},
                        json=body,
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for m in data.get("matches") or []:
                        threat = m.get("threat") or {}
                        u = threat.get("url")
                        if u:
                            malicious_raw.add(u)
        except Exception:
            return set()

        return malicious_raw

    def _is_url_flagged_by_gsb(
        self,
        original: str,
        final_url: str,
        malicious_raw: set[str],
    ) -> bool:
        if not malicious_raw:
            return False
        for cand in (original, final_url):
            if cand in malicious_raw:
                return True
            nc = _normalize_url_for_compare(cand)
            for mu in malicious_raw:
                if _normalize_url_for_compare(mu) == nc:
                    return True
        return False

    def heuristic_check(self, url: str) -> tuple[bool, str]:
        """
        啟發式檢查：
        - Punycode: 'xn--' in domain
        - 可疑 TLD: 符合 SUSPICIOUS_TLDS
        回傳 (is_suspicious, reason)
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            host = (parsed.netloc or parsed.path or "").lower()
            if "@" in host:
                host = host.split("@")[-1]
            domain = host.split(":")[0]
        except Exception:
            return False, ""

        if not domain:
            return False, ""

        if "xn--" in domain:
            return True, "偵測到 Punycode 國際化網域（xn--），可能用於仿冒"

        for suffix in sorted(SUSPICIOUS_TLDS, key=len, reverse=True):
            if domain.endswith(suffix):
                return True, f"可疑頂級網域（{suffix}）"

        return False, ""

    def _row_from_scan(
        self,
        original: str,
        final_url: str,
        hops: int,
        malicious_set: set[str],
    ) -> dict:
        is_malicious = self._is_url_flagged_by_gsb(
            original, final_url, malicious_set
        )
        is_suspicious, heuristic_reason = self.heuristic_check(final_url)

        if is_malicious:
            return {
                "final_url": final_url,
                "trust_score": 0,
                "label": "Malicious",
                "reason": "Google Safe Browsing 標記為惡意網站",
            }
        if is_suspicious:
            return {
                "final_url": final_url,
                "trust_score": 40,
                "label": "Suspicious",
                "reason": heuristic_reason,
            }
        if hops >= 0 and hops > 3:
            return {
                "final_url": final_url,
                "trust_score": 50,
                "label": "Suspicious",
                "reason": f"偵測到 {hops} 層重新導向，可能為追蹤連結",
            }
        return {
            "final_url": final_url,
            "trust_score": 90,
            "label": "Safe",
            "reason": "未發現已知威脅",
        }

    async def analyze_batch(self, urls: list[str]) -> list[dict]:
        """
        並行追蹤重新導向後，將「原始 + 最終」URL 去重並批次送 GSB（必要時分多批 500）。
        回傳與 urls 同序的結果 dict 列表。
        """
        if not urls:
            return []

        redirects = await asyncio.gather(
            *[self.get_final_url(u) for u in urls],
            return_exceptions=True,
        )

        pairs: list[tuple[str, str, int]] = []
        for i, u in enumerate(urls):
            r = redirects[i]
            if isinstance(r, BaseException):
                pairs.append((u, u, -1))
            else:
                pairs.append((u, r[0], r[1]))

        to_check: list[str] = []
        seen: set[str] = set()
        for orig, fin, _ in pairs:
            for x in (orig, fin):
                if x and x not in seen:
                    seen.add(x)
                    to_check.append(x)

        malicious_set: set[str] = set()
        if to_check:
            malicious_set = await self.check_google_safe_browsing_batch(to_check)

        return [
            self._row_from_scan(orig, fin, hops, malicious_set)
            for orig, fin, hops in pairs
        ]

    async def analyze_url(self, url: str) -> dict:
        """單一 URL 完整分析，回傳 UrlScanResult 相容的 dict"""
        rows = await self.analyze_batch([url])
        return rows[0]

    def analyze(self, content: str) -> dict:
        """BaseDetector 介面相容（同步包裝，供測試用）"""
        return asyncio.run(self.analyze_url(content))
