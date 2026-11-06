"""暫時 debug：把帶毫秒時間戳的訊息寫到設定檔同資料夾的 debug.log，確認完就拿掉。"""

import time

from gt import config


def log(msg):
    path = config.config_path().with_name("debug.log")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')}.{int(time.time() * 1000) % 1000:03d} {msg}\n")
