from abc import ABC, abstractmethod


class BaseDetector(ABC):
    @abstractmethod
    def analyze(self, content: str) -> dict:
        """回傳包含 trust_score, label, reason 的 dict"""
        raise NotImplementedError
