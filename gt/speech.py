"""聆聽：偵測文字的語言、比對系統語音的 locale、向 OpenAI 取得語音。純邏輯，不依賴 Qt。

網路請求層 post(url, payload, headers) -> (狀態碼, 回應內容 bytes) 由外部注入，測試以假回應取代。
"""

import http.client
import json
import urllib.parse

from dataclasses import dataclass

from gt.translate import http_post

# Cloud Translation - Basic (v2) detect：https://docs.cloud.google.com/translate/docs/reference/rest/v2/detect
DETECT_URL = "https://translation.googleapis.com/language/translate/v2/detect"
# OpenAI 語音：https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "alloy"


@dataclass
class Speech:
    """聆聽的準備結果：locale 有值時用系統語音播放；audio 為 OpenAI 回傳的 mp3；error 為失敗原因。"""
    locale: str = None
    audio: bytes = None
    error: str = None


def detect_language(text, api_key, post=http_post):
    """以 Google 偵測 text 的語言，回傳語言代碼（例如 "ja"、"zh-TW"）；
    未設定 API key、請求失敗或回應無法解析時回傳 None。"""
    if not api_key:
        return None
    try:
        status, body = post(f"{DETECT_URL}?{urllib.parse.urlencode({'key': api_key})}", {"q": text}, None)
        if status != 200:
            return None
        lang = json.loads(body)["data"]["detections"][0][0]["language"]
    except (OSError, ValueError, http.client.HTTPException, KeyError, IndexError, TypeError):
        return None
    return lang if isinstance(lang, str) else None


def match_locale(lang, locales):
    """locales（QLocale.name() 格式，例如 "zh_TW"）中與語言代碼 lang 相符的第一個；沒有回傳 None。
    中文要語言與地區都相同（zh-TW 只對 zh_TW），其他語言只比語言。"""
    want = lang.replace("-", "_").split("_")
    for name in locales:
        have = name.split("_")
        if have[0].lower() != want[0].lower():
            continue
        if want[0].lower() != "zh" or [p.upper() for p in have[1:2]] == [p.upper() for p in want[1:2]]:
            return name
    return None


def openai_speech(text, base_url, api_key, post=http_post):
    """POST {base_url}/audio/speech 取得 text 的 mp3 語音；成功時 Speech.audio 為 mp3 內容，
    失敗時 Speech.error 為原因（連線失敗、請求失敗、HTTP {狀態碼}：{伺服器訊息}、HTTP {狀態碼}）。"""
    try:
        status, body = post(f"{base_url.rstrip('/')}/audio/speech",
                            {"model": TTS_MODEL, "voice": TTS_VOICE, "input": text, "response_format": "mp3"},
                            {"Authorization": f"Bearer {api_key}"})
    except OSError as e:                                # 逾時、DNS、連不上
        return Speech(error=f"連線失敗：{e}")
    except (ValueError, http.client.HTTPException) as e:  # 例如未設定 base URL
        return Speech(error=f"請求失敗：{e}")
    if status == 200:
        return Speech(audio=body)
    try:
        return Speech(error=f"HTTP {status}：{json.loads(body)['error']['message']}")
    except (ValueError, KeyError, TypeError):
        return Speech(error=f"HTTP {status}")


def prepare(text, cfg, locales, post=http_post):
    """聆聽 text 的準備（背景執行緒）：偵測語言，locales（系統語音的 QLocale.name() 清單）有相符者時
    回傳 Speech(locale=...)；沒有相符或偵測失敗時回傳 OpenAI 語音的結果。"""
    lang = detect_language(text, cfg["google_api_key"], post)
    locale = match_locale(lang, locales) if lang else None
    if locale:
        return Speech(locale=locale)
    return openai_speech(text, cfg["openai_base_url"], cfg["openai_api_key"], post)
