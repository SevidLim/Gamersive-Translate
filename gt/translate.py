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
from typing import Callable, NamedTuple

AUTO = "auto"
LANG_NAMES = {"zh-TW": "繁體中文"}                 # 語言代碼 → 語言名稱
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
    MAX_Q = 128                                         # 一次請求的 q 陣列上限（官方文件）

    def __init__(self, api_key, post=http_post):
        self.api_key = api_key
        self.post = post

    def translate(self, text, source, target, by_line=False):
        """by_line 為 True 時每行（略過空行）各為一個 q，每 MAX_Q 行送一次請求，譯文依序以換行串回。"""
        if not self.api_key:
            return Result(self.name, error="未設定 API key")
        if not by_line:
            return self._send(text, source, target, lambda d: d["data"]["translations"][0]["translatedText"])
        lines = [line for line in text.split("\n") if line.strip()]
        parts = []
        for i in range(0, len(lines), self.MAX_Q):
            r = self._send(lines[i:i + self.MAX_Q], source, target,
                           lambda d: "\n".join(t["translatedText"] for t in d["data"]["translations"]))
            if r.error is not None:
                return r
            parts.append(r.text)
        return Result(self.name, text="\n".join(parts))

    def _send(self, q, source, target, read_text):
        payload = {"q": q, "target": target, "format": "text"}
        if source != AUTO:
            payload["source"] = source
        return _request(self.name, self.post, f"{self.URL}?{urllib.parse.urlencode({'key': self.api_key})}", payload, None,
                        read_text, _error_message)


def _messages(text, target):
    """LLM 引擎共用的提示：system 指示翻譯方向，user 為原文。"""
    return [{"role": "system", "content": f"把使用者的文字翻成 {target}，只輸出譯文。"},
            {"role": "user", "content": text}]


def _error_message(d):
    """Google 與 OpenAI 相容共用的錯誤格式：{"error": {"message": "..."}}。"""
    return d["error"]["message"]


def _missing_model(name, model):
    """LLM 引擎共用的模型檢查：未設定時回傳失敗 Result，否則 None。"""
    if not model:
        return Result(name, error="未設定模型")
    return None


def _join_url(base, path):
    """LLM 引擎共用的 URL 組合：去掉 base 結尾的 /，再接上 path。"""
    return f"{base.rstrip('/')}{path}"


def _request(name, post, url, payload, headers, read_text, read_error):
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
        if missing := _missing_model(self.name, self.model):
            return missing
        headers = {"Authorization": f"Bearer {self.api_key}"}
        return _request(self.name, self.post, _join_url(self.base_url, "/chat/completions"),
                        {"model": self.model, "messages": _messages(text, target)}, headers,
                        lambda d: d["choices"][0]["message"]["content"], _error_message)


class OllamaTranslator:
    """Ollama /api/chat，stream 關閉時回傳單一 JSON；錯誤為 {"error": "..."}。
    https://docs.ollama.com/api/chat、https://docs.ollama.com/api/errors"""

    name = "Ollama"

    def __init__(self, endpoint, model, post=http_post):
        self.endpoint, self.model, self.post = endpoint, model, post

    def translate(self, text, source, target):
        if not self.endpoint:
            return Result(self.name, error="未設定端點")
        if missing := _missing_model(self.name, self.model):
            return missing
        return _request(self.name, self.post, _join_url(self.endpoint, "/api/chat"),
                        {"model": self.model, "messages": _messages(text, target), "stream": False}, None,
                        lambda d: d["message"]["content"], lambda d: d["error"])


class Field(NamedTuple):
    config_key: str                                     # config 欄位
    placeholder: str                                    # 輸入框提示文字
    secret: bool                                        # 是否遮罩


@dataclass
class Engine:
    name: str                                           # 顯示名稱，取自引擎類別的 name
    fields: list                                        # 設定欄位：Field 串列
    build: Callable                                     # cfg -> 翻譯引擎


# 引擎表：key 為 cfg["engine"] 的值
ENGINES = {
    "google": Engine(GoogleTranslator.name, [Field("google_api_key", "Google API key", True)],
                     lambda cfg: GoogleTranslator(cfg["google_api_key"], http_post)),
    "openai": Engine(OpenAICompatibleTranslator.name,
                     [Field("openai_base_url", "base URL", False), Field("openai_api_key", "API key", True),
                      Field("openai_model", "model", False)],
                     lambda cfg: OpenAICompatibleTranslator(cfg["openai_base_url"], cfg["openai_api_key"],
                                                            cfg["openai_model"], http_post)),
    "ollama": Engine(OllamaTranslator.name, [Field("ollama_endpoint", "endpoint", False), Field("ollama_model", "model", False)],
                     lambda cfg: OllamaTranslator(cfg["ollama_endpoint"], cfg["ollama_model"], http_post)),
}


def make_translator(cfg):
    """依 cfg["engine"] 從引擎表建立翻譯引擎；不在表中時用 Google。"""
    return ENGINES.get(cfg["engine"], ENGINES["google"]).build(cfg)
