# Gamersive-Translate

遊戲中使用的翻譯工具，平時收在螢幕右緣，需要時展開，不打斷遊玩。

## Language

### 介面

**邊條**:
面板收合時露在螢幕右緣的細條，滑鼠停留後展開面板。
_Avoid_: 把手、tab

**面板**:
展開後的翻譯主視窗，含文字翻譯頁與 OCR 頁。
_Avoid_: 視窗、浮窗

**文字翻譯頁**:
面板中輸入原文、顯示譯文的分頁。

**OCR 頁**:
面板中擷取畫面文字並翻譯的分頁。

### OCR

**截圖區域**:
OCR 擷取的畫面範圍：全畫面、上半部、下半部，或複選的九宮格格子。

**OCR 引擎**:
輸入圖片、輸出依閱讀順序排列的文字區塊的辨識服務；主引擎 Surya，備用依序為 RapidOCR PP-OCRv5 mobile、PP-OCRv6 small。

**文字區塊**:
OCR 引擎輸出的一段文字；RapidOCR 為一行一個區塊；Surya 為一個區塊一個文字區塊。

### 翻譯

**翻譯引擎（engine）**:
把原文翻成譯文的服務，可選 Google、OpenAI 相容或 Ollama，由設定的 engine 決定。
_Avoid_: 翻譯器、後端

**Google**:
使用 Google Cloud Translation（Basic v2）的翻譯引擎，以 API key 認證。

**OpenAI 相容（OpenAI-compatible）**:
使用 OpenAI Chat Completions 格式 API 的翻譯引擎，可接任何相容的服務。

**Ollama**:
使用本機 Ollama 服務 /api/chat 的翻譯引擎。

**base URL**:
OpenAI 相容引擎的 API 根網址，請求送到 {base URL}/chat/completions。

**API key（金鑰）**:
翻譯引擎用來認證的金鑰；Google 放在網址參數，OpenAI 相容以 Bearer 標頭送出。
_Avoid_: token

**模型（model）**:
OpenAI 相容與 Ollama 引擎用來翻譯的模型名稱。

**端點（endpoint）**:
Ollama 的服務網址，預設 http://localhost:11434。
