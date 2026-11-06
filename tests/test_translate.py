"""翻譯引擎：在網路請求層以假回應取代真實 API，驗證請求內容、譯文解析、失敗回傳。"""

import http.client
import json

from gt.translate import AUTO, GoogleTranslator, OllamaTranslator, OpenAICompatibleTranslator, make_translator


class FakePost:
    """假的網路請求層：記下收到的請求，回傳預先給定的 (狀態碼, 回應內容)。"""

    def __init__(self, status=200, body=b"{}", error=None):
        self.status, self.body, self.error = status, body, error
        self.calls = []

    def __call__(self, url, payload, headers=None):
        self.calls.append((url, payload))
        self.headers = headers
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


def test_api_key_with_special_characters_is_url_encoded():
    post = FakePost(body=ok_body("你好"))
    GoogleTranslator("a b&c/金鑰", post).translate("Hello", AUTO, "zh-TW")
    url, _ = post.calls[0]
    assert url.endswith("?key=a+b%26c%2F%E9%87%91%E9%91%B0")


def test_invalid_request_returns_reason_instead_of_raising():
    post = FakePost(error=http.client.InvalidURL("URL can't contain control characters"))
    r = GoogleTranslator("KEY", post).translate("Hello", AUTO, "zh-TW")
    assert r.engine == "Google"
    assert r.text is None
    assert r.error.startswith("請求失敗：")


def openai_body(text):
    return json.dumps({"choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]}).encode()


def ollama_body(text):
    return json.dumps({"model": "m", "message": {"role": "assistant", "content": text}, "done": True}).encode()


def test_openai_request_content():
    post = FakePost(body=openai_body("你好"))
    OpenAICompatibleTranslator("https://api.example.com/v1/", "SK", "gpt-x", post).translate("Hello", AUTO, "zh-TW")
    url, payload = post.calls[0]
    assert url == "https://api.example.com/v1/chat/completions"
    assert post.headers == {"Authorization": "Bearer SK"}
    assert payload == {"model": "gpt-x", "messages": [
        {"role": "system", "content": "把使用者的文字翻成 zh-TW，只輸出譯文。"},
        {"role": "user", "content": "Hello"}]}


def test_openai_explicit_source_in_prompt_and_no_key_no_auth_header():
    post = FakePost(body=openai_body("你好"))
    OpenAICompatibleTranslator("http://h/v1", "", "m", post).translate("Hola", "es", "zh-TW")
    assert post.headers == {}
    assert post.calls[0][1]["messages"][0]["content"] == "把使用者的文字從 es 翻成 zh-TW，只輸出譯文。"


def test_openai_parses_translation():
    r = OpenAICompatibleTranslator("http://h/v1", "K", "m", FakePost(body=openai_body("你好，世界"))).translate("Hi", AUTO, "zh-TW")
    assert (r.engine, r.text, r.error) == ("OpenAI 相容", "你好，世界", None)


def test_openai_api_error_message():
    body = json.dumps({"error": {"message": "Incorrect API key provided", "type": "invalid_request_error"}}).encode()
    r = OpenAICompatibleTranslator("http://h/v1", "BAD", "m", FakePost(status=401, body=body)).translate("Hi", AUTO, "zh-TW")
    assert (r.engine, r.text, r.error) == ("OpenAI 相容", None, "HTTP 401：Incorrect API key provided")


def test_openai_failures():
    t = lambda post: OpenAICompatibleTranslator("http://h/v1", "K", "m", post).translate("Hi", AUTO, "zh-TW")
    assert t(FakePost(error=OSError("timed out"))).error == "連線失敗：timed out"
    assert t(FakePost(status=502, body=b"bad gateway")).error == "HTTP 502"
    assert t(FakePost(body=b"<html>")).error == "回應格式無法解析"


def test_openai_missing_settings_send_nothing():
    post = FakePost()
    assert OpenAICompatibleTranslator("", "K", "m", post).translate("Hi", AUTO, "zh-TW").error == "未設定 base URL"
    assert OpenAICompatibleTranslator("http://h/v1", "K", "", post).translate("Hi", AUTO, "zh-TW").error == "未設定模型"
    assert post.calls == []


def test_ollama_request_content():
    post = FakePost(body=ollama_body("你好"))
    OllamaTranslator("http://localhost:11434/", "llama3", post).translate("Hello", AUTO, "zh-TW")
    url, payload = post.calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert payload == {"model": "llama3", "stream": False, "messages": [
        {"role": "system", "content": "把使用者的文字翻成 zh-TW，只輸出譯文。"},
        {"role": "user", "content": "Hello"}]}


def test_ollama_parses_translation():
    r = OllamaTranslator("http://h:11434", "m", FakePost(body=ollama_body("你好"))).translate("Hi", AUTO, "zh-TW")
    assert (r.engine, r.text, r.error) == ("Ollama", "你好", None)


def test_ollama_failures():
    t = lambda post: OllamaTranslator("http://h:11434", "m", post).translate("Hi", AUTO, "zh-TW")
    body = json.dumps({"error": "model 'm' not found"}).encode()
    assert (t(FakePost(status=404, body=body)).engine, t(FakePost(status=404, body=body)).error) == ("Ollama", "HTTP 404：model 'm' not found")
    assert t(FakePost(error=OSError("refused"))).error == "連線失敗：refused"
    assert t(FakePost(body=b"{}")).error == "回應格式無法解析"


def test_ollama_missing_model_sends_nothing():
    post = FakePost()
    assert OllamaTranslator("http://h:11434", "", post).translate("Hi", AUTO, "zh-TW").error == "未設定模型"
    assert post.calls == []


def test_make_translator_uses_selected_engine(monkeypatch):
    import gt.translate as t
    post = FakePost(body=b"{}")
    monkeypatch.setattr(t, "http_post", post)
    cfg = {"engine": "google", "google_api_key": "G", "openai_base_url": "http://o/v1", "openai_api_key": "",
           "openai_model": "m", "ollama_endpoint": "http://l:11434", "ollama_model": "q"}
    for engine, url, name in [("google", "https://translation.googleapis.com/language/translate/v2?key=G", "Google"),
                              ("openai", "http://o/v1/chat/completions", "OpenAI 相容"),
                              ("ollama", "http://l:11434/api/chat", "Ollama")]:
        r = make_translator({**cfg, "engine": engine}).translate("Hi", AUTO, "zh-TW")
        assert (post.calls[-1][0], r.engine) == (url, name)
