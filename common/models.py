from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import List, Optional
from datetime import datetime
import re

from .validators import assert_public_http_url

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
        # 簡單的 SSRF 防護：禁止私有 IP
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
        
        # 防止日誌注入：移除換行符號並回傳字串
        return url_str.replace("\r", "").replace("\n", "")


class BatchUrlRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=100)
    # False = 輕量模式：跳過 server 端 redirect 追蹤（僅 GSB + 啟發式），供整頁批次掃描降載
    follow_redirects: bool = True

    @field_validator("urls")
    @classmethod
    def check_urls(cls, v: List[str]) -> List[str]:
        for url in v:
            if not url or not url.strip():
                raise ValueError("urls 中不可包含空字串")
            assert_public_http_url(url.strip())
        return v


class BehaviorFeatures(BaseModel):
    """頁面行為特徵（由 content.js 以 DOM 啟發式擷取）。"""
    password_field_count: int = Field(0, ge=0, le=1000)
    external_password_form: bool = False
    form_action_external: bool = False
    hidden_input_count: int = Field(0, ge=0, le=10000)
    iframe_count: int = Field(0, ge=0, le=10000)
    cross_origin_iframe_count: int = Field(0, ge=0, le=10000)
    transparent_overlay: bool = False
    obfuscated_script: bool = False
    dynamic_script_inject: int = Field(0, ge=0, le=100000)
    suspicious_tld: bool = False


class BehaviorRequest(BaseModel):
    url: Optional[HttpUrl] = None
    features: BehaviorFeatures

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[HttpUrl]) -> Optional[str]:
        if v is None:
            return None
        url_str = str(v)
        private_patterns = [
            r"^https?://localhost",
            r"^https?://127\.",
            r"^https?://192\.168\.",
            r"^https?://10\.",
            r"^https?://172\.(1[6-9]|2[0-9]|3[0-1])\.",
        ]
        for pattern in private_patterns:
            if re.match(pattern, url_str):
                raise ValueError("不允許私有網路 URL")
        return url_str.replace("\r", "").replace("\n", "")
