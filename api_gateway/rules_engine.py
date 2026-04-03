import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class RulesEngine:
    def __init__(self):
        # 典型詐騙模式 (Regex)
        self.SCAM_PATTERNS = [
            (r"加.*LINE", "偵測到誘導私下聯絡關鍵字 (LINE)"),
            (r"飆股|老師帶路|穩賺不賠", "偵測到典型投資詐騙用語"),
            (r"中獎|領取.*獎金", "偵測到中獎誘騙關鍵字"),
            (r"帳號.*異常|重新登入", "偵測到釣魚登入誘導")
        ]
        # 危險網域黑名單 (精確匹配 hostname)
        self.BLACK_DOMAINS = {"scam-site.com", "bit.ly", "cutt.ly"}

    def check(self, content: str, url: str = None):
        """
        回傳字典: {"hit": bool, "trust_score": int, "reason": str}
        """
        # 1. 檢查 URL (精確比對 hostname)
        if url:
            try:
                parsed_url = urlparse(url)
                hostname = parsed_url.hostname.lower() if parsed_url.hostname else ""
                
                # 檢查是否完全符合黑名單，或屬於黑名單網域的子網域
                for domain in self.BLACK_DOMAINS:
                    if hostname == domain or hostname.endswith(f".{domain}"):
                        return {
                            "hit": True, 
                            "trust_score": 10, 
                            "reason": f"警報：來源網域 {domain} 具有高度風險。"
                        }
            except Exception as e:
                logger.warning("[RulesEngine] URL 解析失敗: %s", e)

        # 2. 檢查文字 Regex
        for pattern, reason in self.SCAM_PATTERNS:
            if re.search(pattern, content):
                return {
                    "hit": True, 
                    "trust_score": 15, 
                    "reason": reason
                }

        return {"hit": False}

# 實例化供外部導入
engine = RulesEngine()