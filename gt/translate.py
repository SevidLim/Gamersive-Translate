"""翻譯引擎。

共同介面：translate(原文, 來源語言, 目標語言) -> Result。
成功時 Result.text 為譯文；失敗時 Result.error 為原因，Result.engine 為引擎名稱。
來源語言傳 AUTO 表示自動偵測。

網路請求層 post(url, payload) -> (狀態碼, 回應內容 bytes) 由外部注入，測試以假回應取代。
"""

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

AUTO = "auto"
TIMEOUT_S = 10


@dataclass
class Result:
    engine: str
    text: str = None
    error: str = None


def http_post(url, payload):
    """以 JSON 送出 POST；HTTP 錯誤狀態也回傳 (狀態碼, 內容)，連線失敗則丟出 OSError。"""
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class GoogleTranslator:
    """Cloud Translation - Basic (v2)：API key 認證，不帶 source 時自動偵測。
    https://docs.cloud.google.com/translate/docs/reference/rest/v2/translate"""

    name = "Google"
    URL = "https://translation.googleapis.com/language/translate/v2"

    def __init__(self, api_key, post=http_post):
        self.api_key = api_key
        self.post = post

    def translate(self, text, source, target):
        if not self.api_key:
            return Result(self.name, error="未設定 API key")
        payload = {"q": text, "target": target, "format": "text"}
        if source != AUTO:
            payload["source"] = source
        try:
            status, body = self.post(f"{self.URL}?{urllib.parse.urlencode({'key': self.api_key})}", payload)
        except OSError as e:                            # 逾時、DNS、連不上
            return Result(self.name, error=f"連線失敗：{e}")
        except (ValueError, http.client.HTTPException) as e:  # 例如 URL 含控制字元（http.client.InvalidURL）
            return Result(self.name, error=f"請求失敗：{e}")
        try:
            data = json.loads(body)
            if status != 200:
                return Result(self.name, error=f"HTTP {status}：{data['error']['message']}")
            return Result(self.name, text=data["data"]["translations"][0]["translatedText"])
        except (ValueError, KeyError, IndexError, TypeError):
            if status != 200:
                return Result(self.name, error=f"HTTP {status}")
            return Result(self.name, error="回應格式無法解析")
