"""設定檔 %LOCALAPPDATA%\\Gamersive-Translate\\config.json 的讀寫。"""

import copy
import json
import os
from pathlib import Path

APP_NAME = "Gamersive-Translate"

DEFAULTS = {
    "config_version": 1,
    "google_api_key": "",
    "source_lang": "auto",                      # 自動偵測
    "target_lang": "zh-TW",                     # 繁體中文
    "engine": "google",
    "openai_base_url": "",
    "openai_api_key": "",
    "openai_model": "",
    "ollama_endpoint": "http://localhost:11434",
    "ollama_model": "",
}


def config_path():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    return Path(base) / APP_NAME / "config.json"


def load(path=None):
    """讀設定；檔案不存在就建立並寫入預設值。"""
    path = Path(path or config_path())
    if not path.exists():
        cfg = copy.deepcopy(DEFAULTS)
        save(cfg, path)
        return cfg
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {**copy.deepcopy(DEFAULTS), **data}


def save(cfg, path=None):
    path = Path(path or config_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
