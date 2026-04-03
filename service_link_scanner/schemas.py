from pydantic import BaseModel
from typing import List


class UrlScanResult(BaseModel):
    url: str
    final_url: str
    trust_score: int
    label: str
    reason: str


class BatchUrlResponse(BaseModel):
    results: List[UrlScanResult]
