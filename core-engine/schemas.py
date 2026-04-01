from pydantic import BaseModel
from typing import List, Optional


class SecurityRequest(BaseModel):
    request_id: str
    payload_type: str  # "text" 或 "image"
    content: str       # 文字內容或 Base64 影像
    url: Optional[str] = None


class SecurityResponse(BaseModel):
    request_id: str
    trust_score: int
    label: str
    reason: str


class UrlScanResult(BaseModel):
    url: str
    final_url: str
    trust_score: int
    label: str
    reason: str


class BatchUrlRequest(BaseModel):
    urls: List[str]


class BatchUrlResponse(BaseModel):
    results: List[UrlScanResult]
