from pydantic import BaseModel
from typing import List


class UrlScanResult(BaseModel):
    url: str
    final_url: str
    trust_score: int
    label: str
    reason: str
    hop_count: int = -1


class BatchUrlResponse(BaseModel):
    results: List[UrlScanResult]
