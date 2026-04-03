from pydantic import BaseModel, Field, field_validator
from typing import List


class UrlScanResult(BaseModel):
    url: str
    final_url: str
    trust_score: int
    label: str
    reason: str


class BatchUrlRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=100)

    @field_validator("urls")
    @classmethod
    def check_urls(cls, v: List[str]) -> List[str]:
        for url in v:
            if not url or not url.strip():
                raise ValueError("urls 中不可包含空字串")
        return v


class BatchUrlResponse(BaseModel):
    results: List[UrlScanResult]
