from pydantic import BaseModel
from typing import Optional


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
