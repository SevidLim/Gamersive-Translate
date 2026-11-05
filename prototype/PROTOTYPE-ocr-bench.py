"""PROTOTYPE（用完即丟，不進 main）

要回答的問題：
  在這台電腦、遊戲進行中，dxcam 截圖 + RapidOCR（PP-OCRv6 small，ONNX Runtime CPU）
  能否在可接受的時間內，準確辨識遊戲畫面上的英文／日文／中文？

用法：
  python PROTOTYPE-ocr-bench.py --region full|top|bottom
  python PROTOTYPE-ocr-bench.py --cells 3,6        # 九宮格複選，1-9 由左上到右下，取外框
  可加 --ver v6|v5（預設 v6）、--delay 5（倒數秒數，切回遊戲用）、--runs 3（重複辨識次數）、--output 0（螢幕編號）
"""
import argparse
import time
from pathlib import Path

import cv2
import dxcam
from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

VERSIONS = {
    "v6": {},  # rapidocr 3.10.0 預設即 PP-OCRv6 small
    "v5": {"Det.ocr_version": OCRVersion.PPOCRV5, "Det.model_type": ModelType.MOBILE,
           "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE},
    # v5 東斯拉夫模型：官方標示 Russian, Belarusian, Ukrainian, English
    "v5-eslav": {"Det.ocr_version": OCRVersion.PPOCRV5, "Det.model_type": ModelType.MOBILE,
                 "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE,
                 "Rec.lang_type": LangRec.ESLAV},
}


def crop_box(w, h, region, cells):
    if cells:
        cs = [int(c) for c in cells.split(",")]
        cols = [(c - 1) % 3 for c in cs]
        rows = [(c - 1) // 3 for c in cs]
        return (min(cols) * w // 3, min(rows) * h // 3,
                (max(cols) + 1) * w // 3, (max(rows) + 1) * h // 3)
    return {"full": (0, 0, w, h), "top": (0, 0, w, h // 2), "bottom": (0, h // 2, w, h)}[region]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="full", choices=["full", "top", "bottom"])
    ap.add_argument("--cells", default="")
    ap.add_argument("--delay", type=int, default=5)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--output", type=int, default=0)
    ap.add_argument("--ver", default="v6", choices=list(VERSIONS))
    ap.add_argument("--image", default="")
    a = ap.parse_args()

    t = time.perf_counter()
    engine = RapidOCR(params=VERSIONS[a.ver] or None)
    print(f"[建立 OCR 引擎 {a.ver}] {time.perf_counter() - t:.2f}s（模型在第 1 次辨識時才載入）")

    if a.image:                               # 用已存的截圖重跑，不截新圖
        img = cv2.imread(a.image)
        print(f"[讀取截圖] {a.image}  {img.shape[1]}x{img.shape[0]}")
    else:
        cam = dxcam.create(output_idx=a.output, output_color="BGR")
        for i in range(a.delay, 0, -1):
            print(f"{i} 秒後截圖，請切回遊戲…")
            time.sleep(1)

        t = time.perf_counter()
        frame = None
        while frame is None:                  # one-shot 模式沒有新畫面時會回傳 None
            frame = cam.grab()
        t_cap = time.perf_counter() - t
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = crop_box(w, h, a.region, a.cells)
        img = frame[y1:y2, x1:x2]
        out = Path(__file__).with_name(f"PROTOTYPE-shot-{time.strftime('%H%M%S')}.png")
        cv2.imwrite(str(out), img)
        print(f"[截圖] {t_cap * 1000:.0f}ms  螢幕 {w}x{h}  區域 {(x1, y1, x2, y2)}  已存 {out.name}")

    res = None
    for r in range(1, a.runs + 1):
        t = time.perf_counter()
        res = engine(img)
        print(f"[辨識 第{r}次] 總 {time.perf_counter() - t:.2f}s  elapse_list(det,cls,rec)={res.elapse_list}")

    print("\n===== 辨識結果 =====")
    for txt, score in zip(res.txts or (), res.scores or ()):
        print(f"{score:.2f}  {txt}")


if __name__ == "__main__":
    main()
