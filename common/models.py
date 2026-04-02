from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Optional
from datetime import datetime
import re

class AnalyzeRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    url: Optional[HttpUrl] = None
    timestamp: Optional[str] = None

    @field_validator("content")
    @classmethod
    def strip_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content 不可為空白")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            # 驗證是否為 ISO 格式
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            # 防止日誌注入：只允許特定字元
            if not re.match(r"^[0-9T\-:Z.+]+$", v):
                raise ValueError("無效的時間戳記格式")
            return v
        except ValueError:
            raise ValueError("無效的時間戳記格式")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[HttpUrl]) -> Optional[str]:
        if v is None:
            return None
        url_str = str(v)
        # 簡單的 SSRF 防護：禁止私有 IP (這只是基本範例，生產環境建議用更嚴格的檢查)
        private_patterns = [
            r"^https?://localhost",
            r"^https?://127\.",
            r"^https?://192\.168\.",
            r"^https?://10\.",
            r"^https?://172\.(1[6-9]|2[0-9]|3[0-1])\."
        ]
        for pattern in private_patterns:
            if re.match(pattern, url_str):
                raise ValueError("不允許私有網路 URL")
        
        # 防止日誌注入：移除換行符號
        return HttpUrl(url_str.replace("\r", "").replace("\n", ""))
