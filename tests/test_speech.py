"""聆聽：在網路請求層以假回應取代真實 API，驗證語言偵測、語音 locale 比對、OpenAI 語音請求與失敗回傳。"""

import json

from gt import speech


class FakePost:
    """假的網路請求層：記下收到的請求，依序回傳預先給定的 (狀態碼, 回應內容)，或丟出例外。"""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, url, payload, headers=None):
        self.calls.append((url, payload, headers))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def detect_body(lang):
    return json.dumps({"data": {"detections": [[{"language": lang, "isReliable": False, "confidence": 0.98}]]}}).encode()


def test_detect_sends_text_and_url_encoded_key_and_returns_language():
    post = FakePost((200, detect_body("ja")))
    assert speech.detect_language("こんにちは", "a b&c", post) == "ja"
    url, payload, _ = post.calls[0]
    assert url == "https://translation.googleapis.com/language/translate/v2/detect?key=a+b%26c"
    assert payload == {"q": "こんにちは"}


def test_detect_without_api_key_returns_none_without_sending_request():
    post = FakePost()
    assert speech.detect_language("Hello", "", post) is None
    assert post.calls == []


def test_detect_failure_returns_none():
    detect = lambda reply: speech.detect_language("Hello", "K", FakePost(reply))
    assert detect(OSError("timed out")) is None                          # 連線失敗
    assert detect(ValueError("bad url")) is None                         # 請求失敗
    assert detect((403, b'{"error": {"message": "API key not valid"}}')) is None
    assert detect((200, b"<html>")) is None                              # 回應格式無法解析
    assert detect((200, b'{"data": {"detections": []}}')) is None


LOCALES = ["en_US", "en_GB", "zh_TW", "zh_CN", "ja_JP"]              # QLocale.name() 的格式


def test_match_locale_by_language():
    assert speech.match_locale("ja", LOCALES) == "ja_JP"
    assert speech.match_locale("en", LOCALES) == "en_US"             # 同語言多個地區時取第一個


def test_match_locale_chinese_by_region():
    assert speech.match_locale("zh-TW", LOCALES) == "zh_TW"
    assert speech.match_locale("zh-CN", LOCALES) == "zh_CN"
    assert speech.match_locale("zh-TW", ["en_US", "zh_CN"]) is None
    assert speech.match_locale("zh-CN", ["zh_TW", "zh_HK"]) is None


def test_match_locale_without_voice_returns_none():
    assert speech.match_locale("ru", LOCALES) is None
    assert speech.match_locale("ja", []) is None


def test_openai_speech_request_content_and_returns_mp3_bytes():
    post = FakePost((200, b"ID3mp3-bytes"))
    r = speech.openai_speech("Привет", "https://api.example.com/v1/", "SK", post)
    url, payload, headers = post.calls[0]
    assert url == "https://api.example.com/v1/audio/speech"
    assert headers == {"Authorization": "Bearer SK"}
    assert payload == {"model": "gpt-4o-mini-tts", "voice": "alloy", "input": "Привет", "response_format": "mp3"}
    assert (r.audio, r.error) == (b"ID3mp3-bytes", None)


def test_openai_speech_failure_reasons():
    say = lambda reply: speech.openai_speech("Hi", "http://h/v1", "K", FakePost(reply))
    body = json.dumps({"error": {"message": "Incorrect API key provided", "type": "invalid_request_error"}}).encode()
    assert (say((401, body)).audio, say((401, body)).error) == (None, "HTTP 401：Incorrect API key provided")
    assert say((502, b"bad gateway")).error == "HTTP 502"
    assert say(OSError("timed out")).error == "連線失敗：timed out"
    assert say(ValueError("unknown url type")).error == "請求失敗：unknown url type"


CFG = {"google_api_key": "G", "openai_base_url": "http://o/v1", "openai_api_key": "SK"}


def test_prepare_uses_system_voice_when_detected_language_has_one():
    post = FakePost((200, detect_body("zh-TW")))
    r = speech.prepare("你好", CFG, LOCALES, post)
    assert (r.locale, r.audio, r.error) == ("zh_TW", None, None)
    assert len(post.calls) == 1                                      # 只送偵測，不送 OpenAI


def test_prepare_uses_openai_when_no_system_voice():
    post = FakePost((200, detect_body("ru")), (200, b"mp3"))
    r = speech.prepare("Привет", CFG, LOCALES, post)
    assert (r.locale, r.audio, r.error) == (None, b"mp3", None)
    assert post.calls[1][0] == "http://o/v1/audio/speech"


def test_prepare_uses_openai_when_detection_fails():
    post = FakePost((200, b"mp3"))
    r = speech.prepare("Hello", {**CFG, "google_api_key": ""}, LOCALES, post)
    assert (r.locale, r.audio) == (None, b"mp3")
    assert post.calls[0][0] == "http://o/v1/audio/speech"
    post = FakePost(OSError("timed out"), (401, b"{}"))
    assert speech.prepare("Hello", CFG, LOCALES, post).error == "HTTP 401"
