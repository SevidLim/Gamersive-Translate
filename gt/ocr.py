"""OCR 引擎。

共同介面：recognize(圖片) -> 文字區塊清單（list[str]），依閱讀順序排列。
圖片為 BGR 的 numpy 陣列（dxcam、cv2.imread 的格式）。
"""


class RapidOCREngine:
    """RapidOCR 3.10.0 預設參數（PP-OCRv6 small，ONNX Runtime CPU）；一行一個文字區塊，照 RapidOCR 輸出順序。"""

    name = "RapidOCR"

    def __init__(self):
        self._engine = None                      # 第一次辨識時才建立，啟動不等模型載入

    def recognize(self, image):
        if self._engine is None:
            from rapidocr import RapidOCR
            self._engine = RapidOCR()
        return list(self._engine(image).txts or ())
