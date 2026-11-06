"""翻譯引擎：在網路請求層以假回應取代真實 API，驗證請求內容、譯文解析、失敗回傳。"""

import json

from gt.translate import AUTO, GoogleTranslator


class FakePost:
    """假的網路請求層：記下收到的請求，回傳預先給定的 (狀態碼, 回應內容)。"""

    def __init__(self, status=200, body=b"{}", error=None):
        self.status, self.body, self.error = status, body, error
        self.calls = []

    def __call__(self, url, payload):
        self.calls.append((url, payload))
        if self.error:
            raise self.error
        return self.status, self.body


def ok_body(text, detected="en"):
    return json.dumps({"data": {"translations": [
        {"translatedText": text, "detectedSourceLanguage": detected}]}}).encode()


def test_auto_detect_request_omits_source_and_targets_language():
    post = FakePost(body=ok_body("你好"))
    GoogleTranslator("KEY123", post).translate("Hello", AUTO, "zh-TW")
    url, payload = post.calls[0]
    assert url == "https://translation.googleapis.com/language/translate/v2?key=KEY123"
    assert payload == {"q": "Hello", "target": "zh-TW", "format": "text"}


def test_explicit_source_language_is_sent():
    post = FakePost(body=ok_body("你好"))
    GoogleTranslator("K", post).translate("Hola", "es", "zh-TW")
    assert post.calls[0][1]["source"] == "es"


def test_successful_response_returns_translated_text():
    result = GoogleTranslator("K", FakePost(body=ok_body("你好，世界"))).translate("Hello, world", AUTO, "zh-TW")
    assert result.text == "你好，世界"
    assert result.error is None


def test_api_error_returns_engine_name_and_google_message():
    body = json.dumps({"error": {"code": 400, "message": "API key not valid. Please pass a valid API key."}}).encode()
    result = GoogleTranslator("BAD", FakePost(status=400, body=body)).translate("Hello", AUTO, "zh-TW")
    assert result.text is None
    assert result.engine == "Google"
    assert result.error == "HTTP 400：API key not valid. Please pass a valid API key."


def test_network_failure_returns_reason():
    post = FakePost(error=OSError("timed out"))
    result = GoogleTranslator("K", post).translate("Hello", AUTO, "zh-TW")
    assert (result.engine, result.error) == ("Google", "連線失敗：timed out")


def test_missing_api_key_fails_without_sending_request():
    post = FakePost(body=ok_body("你好"))
    result = GoogleTranslator("", post).translate("Hello", AUTO, "zh-TW")
    assert (result.engine, result.error) == ("Google", "未設定 API key")
    assert post.calls == []


def test_unexpected_response_body_returns_reason():
    result = GoogleTranslator("K", FakePost(body=b"<html>oops</html>")).translate("Hello", AUTO, "zh-TW")
    assert (result.engine, result.error) == ("Google", "回應格式無法解析")
