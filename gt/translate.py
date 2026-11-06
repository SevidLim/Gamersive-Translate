"""翻譯引擎。

共同介面：translate(原文, 來源語言, 目標語言) -> Result。
成功時 Result.text 為譯文；失敗時 Result.error 為原因，Result.engine 為引擎名稱。
來源語言傳 AUTO 表示自動偵測。

網路請求層 post(url, payload, headers) -> (狀態碼, 回應內容 bytes) 由外部注入，測試以假回應取代。
"""

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

AUTO = "auto"
TIMEOUT_S = 10


@dataclass
class Result:
    engine: str
    text: str = None
    error: str = None


def http_post(url, payload, headers=None):
    """以 JSON 送出 POST；HTTP 錯誤狀態也回傳 (狀態碼, 內容)，連線失敗則丟出 OSError。"""
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8", **(headers or {})})
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
        return _chat(self.name, self.post, f"{self.URL}?{urllib.parse.urlencode({'key': self.api_key})}", payload, None,
                     lambda d: d["data"]["translations"][0]["translatedText"], lambda d: d["error"]["message"])


def _messages(text, source, target):
    """LLM 引擎共用的提示：system 指示翻譯方向，user 為原文。"""
    return [{"role": "system", "content": f"把使用者的文字翻成 {target}，只輸出譯文。"},
            {"role": "user", "content": text}]


def _chat(name, post, url, payload, headers, read_text, read_error):
    """送出請求並解析；所有引擎共用的錯誤處理。"""
    try:
        status, body = post(url, payload, headers)
    except OSError as e:                                # 逾時、DNS、連不上
        return Result(name, error=f"連線失敗：{e}")
    except (ValueError, http.client.HTTPException) as e:  # 例如 URL 含控制字元
        return Result(name, error=f"請求失敗：{e}")
    try:
        data = json.loads(body)
        if status != 200:
            return Result(name, error=f"HTTP {status}：{read_error(data)}")
        text = read_text(data)
        if not isinstance(text, str):
            raise TypeError
        return Result(name, text=text)
    except (ValueError, KeyError, IndexError, TypeError):
        if status != 200:
            return Result(name, error=f"HTTP {status}")
        return Result(name, error="回應格式無法解析")


class OpenAICompatibleTranslator:
    """OpenAI 相容 Chat Completions：POST {base_url}/chat/completions，Bearer 認證。
    https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create"""

    name = "OpenAI 相容"

    def __init__(self, base_url, api_key, model, post=http_post):
        self.base_url, self.api_key, self.model, self.post = base_url, api_key, model, post

    def translate(self, text, source, target):
        if not self.model:
            return Result(self.name, error="未設定模型")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        return _chat(self.name, self.post, f"{self.base_url.rstrip('/')}/chat/completions",
                     {"model": self.model, "messages": _messages(text, source, target)}, headers,
                     lambda d: d["choices"][0]["message"]["content"], lambda d: d["error"]["message"])


class OllamaTranslator:
    """Ollama /api/chat，stream 關閉時回傳單一 JSON；錯誤為 {"error": "..."}。
    https://docs.ollama.com/api/chat、https://docs.ollama.com/api/errors"""

    name = "Ollama"

    def __init__(self, endpoint, model, post=http_post):
        self.endpoint, self.model, self.post = endpoint, model, post

    def translate(self, text, source, target):
        if not self.endpoint:
            return Result(self.name, error="未設定端點")
        if not self.model:
            return Result(self.name, error="未設定模型")
        return _chat(self.name, self.post, f"{self.endpoint.rstrip('/')}/api/chat",
                     {"model": self.model, "messages": _messages(text, source, target), "stream": False}, None,
                     lambda d: d["message"]["content"], lambda d: d["error"])


@dataclass
class Engine:
    cls: type                                           # 引擎類別，顯示名稱為 cls.name
    fields: list                                        # 設定欄位：(config 欄位, placeholder, 是否遮罩)
    build: Callable                                     # cfg -> 翻譯引擎


# 引擎表：key 為 cfg["engine"] 的值
ENGINES = {
    "google": Engine(GoogleTranslator, [("google_api_key", "Google API key", True)],
                     lambda cfg: GoogleTranslator(cfg["google_api_key"], http_post)),
    "openai": Engine(OpenAICompatibleTranslator,
                     [("openai_base_url", "base URL", False), ("openai_api_key", "API key", True),
                      ("openai_model", "model", False)],
                     lambda cfg: OpenAICompatibleTranslator(cfg["openai_base_url"], cfg["openai_api_key"],
                                                            cfg["openai_model"], http_post)),
    "ollama": Engine(OllamaTranslator, [("ollama_endpoint", "endpoint", False), ("ollama_model", "model", False)],
                     lambda cfg: OllamaTranslator(cfg["ollama_endpoint"], cfg["ollama_model"], http_post)),
}


def make_translator(cfg):
    """依 cfg["engine"] 從引擎表建立翻譯引擎；不在表中時用 Google。"""
    return ENGINES.get(cfg["engine"], ENGINES["google"]).build(cfg)
