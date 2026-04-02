import pytest
from pydantic import ValidationError
from common.models import AnalyzeRequest


# ---------------------------------------------------------------------------
# content field
# ---------------------------------------------------------------------------

class TestContentValidation:
    def test_valid_content(self):
        req = AnalyzeRequest(content="hello world")
        assert req.content == "hello world"

    def test_content_is_stripped(self):
        req = AnalyzeRequest(content="  trimmed  ")
        assert req.content == "trimmed"

    def test_content_at_max_length(self):
        req = AnalyzeRequest(content="a" * 5000)
        assert len(req.content) == 5000

    def test_content_empty_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(content="")

    def test_content_whitespace_only_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(content="   ")

    def test_content_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(content="a" * 5001)

    def test_content_missing_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest()


# ---------------------------------------------------------------------------
# timestamp field
# ---------------------------------------------------------------------------

class TestTimestampValidation:
    def test_timestamp_none_is_valid(self):
        req = AnalyzeRequest(content="hello", timestamp=None)
        assert req.timestamp is None

    @pytest.mark.parametrize("valid_ts", [
        "2023-10-27T10:00:00Z",
        "2023-10-27T10:00:00+05:30",
        "2023-10-27T10:00:00.123456Z",
        "2023-10-27",
        "2024-01-01T00:00:00+00:00",
    ])
    def test_valid_timestamps_accepted(self, valid_ts):
        req = AnalyzeRequest(content="hello", timestamp=valid_ts)
        assert req.timestamp == valid_ts

    @pytest.mark.parametrize("invalid_ts", [
        "not-a-timestamp",
        "invalid-time\n[LOG INJECTION]",
        "2023-10-27 10:00:00",   # space is not in allowed charset
        "2023/10/27T10:00:00Z",  # slash is not in allowed charset
        "2023-10-27T10:00:00\r\n",
    ])
    def test_invalid_timestamps_raise(self, invalid_ts):
        with pytest.raises(ValidationError):
            AnalyzeRequest(content="hello", timestamp=invalid_ts)


# ---------------------------------------------------------------------------
# url field
# ---------------------------------------------------------------------------

class TestUrlValidation:
    def test_url_none_is_valid(self):
        req = AnalyzeRequest(content="hello", url=None)
        assert req.url is None

    @pytest.mark.parametrize("valid_url", [
        "https://example.com",
        "https://google.com/search?q=test",
        "http://172.15.0.1/page",   # 172.15 is NOT in private range
        "http://172.32.0.1/page",   # 172.32 is NOT in private range
    ])
    def test_valid_public_urls_accepted(self, valid_url):
        req = AnalyzeRequest(content="hello", url=valid_url)
        assert req.url is not None

    @pytest.mark.parametrize("private_url", [
        "http://localhost/admin",
        "http://127.0.0.1/",
        "http://127.0.0.2/secret",
        "http://192.168.0.1/",
        "http://192.168.255.255/",
        "http://10.0.0.1/",
        "http://10.255.255.255/",
        "http://172.16.0.1/",
        "http://172.20.0.1/",
        "http://172.31.0.1/",
    ])
    def test_private_urls_blocked(self, private_url):
        with pytest.raises(ValidationError):
            AnalyzeRequest(content="hello", url=private_url)

    def test_invalid_url_format_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(content="hello", url="not-a-url")


# ---------------------------------------------------------------------------
# Full model integration
# ---------------------------------------------------------------------------

class TestFullModel:
    def test_all_fields_valid(self):
        req = AnalyzeRequest(
            content="Valid content",
            url="https://example.com",
            timestamp="2023-10-27T10:00:00Z",
        )
        assert req.content == "Valid content"
        assert req.url is not None
        assert req.timestamp == "2023-10-27T10:00:00Z"

    def test_content_only_is_valid(self):
        req = AnalyzeRequest(content="Only content required")
        assert req.url is None
        assert req.timestamp is None

    def test_model_dump_json_serializable(self):
        req = AnalyzeRequest(
            content="test",
            url="https://example.com",
            timestamp="2023-10-27T10:00:00Z",
        )
        data = req.model_dump(mode="json")
        assert isinstance(data["content"], str)
        assert isinstance(data["url"], str)
        assert isinstance(data["timestamp"], str)
