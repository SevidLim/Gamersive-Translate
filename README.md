# Gamersive-Translate

Windows 遊戲內翻譯工具。平時收在螢幕右緣，需要時展開面板翻譯文字或遊戲畫面，不打斷遊玩。

## 專案資訊

| 項目 | 內容 |
|---|---|
| 位置 | Claude Agents/projects/Gamersive-Translate |
| GitHub | SevidLim/Gamersive-Translate（公開），remote 為 origin |
| 分支 | master；原型在 prototype/ocr-bench |
| 開發流程 | Matt Pocock 主線 skill（按需讀取，母版在 Claude Agents/Workspace/mattpocock-skills） |
| Issue tracker | GitHub Issues，以 gh CLI 操作 |
| 規範檔 | AGENTS.md |
| Domain docs | single-context：根目錄 GLOSSARY.md 與 docs/adr/ |
| 功能代號 | GT |

## 主線進度（GT）

| # | 步驟 | 狀態 |
|---|---|---|
| 0 | 設定 | done |
| 1 | 追問對齊 | done |
| 2 | 原型 | done |
| 3 | 規格（to-spec） | todo |
| 4 | 拆票（to-tickets） | todo |
| 5 | 實作 | todo |
| 6 | PR | todo |
| 7 | 回顧 | todo |

步驟 2 的 handoff 不執行。

## 開發環境

| 項目 | 內容 |
|---|---|
| 作業系統 | Windows 11 Home 25H2（build 26200.7840） |
| 顯示卡 | NVIDIA GeForce RTX 4070，12GB VRAM，驅動 595.79，最高支援 CUDA 13.2 |
| 螢幕 | 主螢幕 2560x1440 |
| Python | 3.10.11 |
| git | 2.49.0.windows.1 |
| gh CLI | 2.103.3，已登入 SevidLim（keyring，https，scope：gist、read:org、repo、workflow） |

## 產品規格

### 技術選型

| 項目 | 決定 |
|---|---|
| GUI 框架 | PySide6，沿用 Desktop-Agent-Pet 的 src/glass.py（Acrylic 毛玻璃、置頂無邊框視窗、側滑動畫） |
| 視覺語彙 | 參考 Quiet Tab（Claude Agents/repos/chrome-newtab）的半透明毛玻璃與按鍵設計，CSS 改寫為 QSS |
| 截圖 | dxcam（DXGI Desktop Duplication） |
| OCR 主引擎 | Surya（surya-ocr 0.23.0）：文字偵測以 torch 在 CPU 執行；辨識由 llama.cpp b11669 CUDA 12.4 版 llama-server 在 GPU 執行，模型 surya-2.5.gguf 與 surya-2.5-mmproj.gguf |
| OCR 備用引擎 | RapidOCR 3.10.0（ONNX Runtime CPU）：PP-OCRv6 small、PP-OCRv5 mobile |
| 設定檔 | %LOCALAPPDATA%\Gamersive-Translate\config.json，API key 一併存放 |

### 支援的遊戲顯示模式

- 支援無邊框視窗化與視窗化。
- 遇到獨佔全螢幕時，面板提示改用無邊框模式。

### 邊條與面板

- 收合時螢幕右緣露出邊條：寬 6px、高 120px、垂直置中、半透明。
- 滑鼠停在邊條 1.5 秒展開面板。
- Alt+Tab 切到本程式時自動展開面板。
- 展開後焦點進入文字翻譯頁的輸入框，不自動截圖。
- 面板失去焦點即收合：點遊戲畫面、Alt+Tab 切走、按 Esc。
- 面板預設貼主螢幕右緣，設定中可切換螢幕。

### 文字翻譯頁

- 上下分屏：上方輸入原文，下方顯示譯文。
- 來源語言預設自動偵測，目標語言預設繁體中文。
- 按 Enter 或翻譯按鈕送出，Shift+Enter 換行。

### OCR 頁

- 版面同文字翻譯頁：上方為辨識出的原文（可修改後重新翻譯），下方為譯文。
- 截圖區域：全畫面、上半部、下半部、九宮格（可複選，截取所選格子的外框矩形）。
- 截圖辨識完成後自動翻譯。
- 畫面上出現任何語言都要自動辨識正確，使用者不手動選語言或換模型。

### 翻譯引擎

| 引擎 | 接法 |
|---|---|
| Google（預設） | 官方 Cloud Translation API，需 API key，每月前 50 萬字元免費 |
| 雲端模型 | OpenAI 相容格式（base URL + key + model），可接 Claude、Gemini、OpenRouter 等 |
| 本地模型 | Ollama /api/chat |

- 第一次啟動預設 Google；設定中可填 key 或改用雲端模型、Ollama。
- 翻譯失敗時，面板底部顯示短暫訊息，寫明引擎與原因，不自動換引擎重試。

### 第一版不做

- 韓文 OCR。

## 詞彙

| 詞 | 定義 | 避免用 |
|---|---|---|
| 邊條 | 面板收合時露在螢幕右緣的細條，滑鼠停留後展開面板 | 把手、tab |
| 面板 | 展開後的翻譯主視窗，含文字翻譯頁與 OCR 頁 | 視窗、浮窗 |
| 文字翻譯頁 | 面板中輸入原文、顯示譯文的分頁 | |
| OCR 頁 | 面板中擷取畫面文字並翻譯的分頁 | |
| 截圖區域 | OCR 擷取的畫面範圍：全畫面、上半部、下半部，或複選的九宮格格子 | |

## 原型（prototype/，分支 prototype/ocr-bench）

### 檔案

| 檔案／資料夾 | 內容 |
|---|---|
| PROTOTYPE-ocr-bench.py | dxcam 截圖或讀已存截圖，RapidOCR 辨識，印出耗時與結果。參數：--ver v6、v5、v5-eslav；--region full、top、bottom；--cells（九宮格 1–9）；--image；--delay；--runs；--output |
| PROTOTYPE-surya.py | Surya 辨識同一張截圖 3 次，印出耗時、記憶體峰值、VRAM 已用。參數為 llama 資料夾名稱（llama.cpp 或 llama.cpp-cuda） |
| PROTOTYPE-memwatch.py | 取樣本程序與子程序的記憶體峰值 |
| .venv | dxcam、rapidocr、onnxruntime |
| .venv-surya | surya-ocr、torch 2.14.1+cpu、psutil |
| llama.cpp | llama.cpp b11669 Windows CPU x64 |
| llama.cpp-cuda | llama.cpp b11669 Windows CUDA 12.4 x64 與 cudart |
| .gitignore | 排除 .venv/、__pycache__/、.venv-*/、llama.cpp/、llama.cpp-cuda/ |

### 實測結果（同一張遊戲截圖，2560x1440，含英文任務文字與俄文標語）

| 項目 | RapidOCR v6 small（CPU） | RapidOCR v5 mobile（CPU） | Surya（GPU） |
|---|---|---|---|
| 不指定語言即可辨識 | 中、英、日、拉丁語系 | 中、英、日 | 91 種語言（中文只列 zh，未區分繁簡） |
| 英文 | 全對 | 有錯字（Jourmal、Take a potatot、1724） | 全對，僅 TAB 圖示辨識為 JAB |
| 俄文 | 亂碼 | 亂碼，Ф 辨識為「中」 | 全對 |
| 熱機後每次耗時 | 約 0.5 秒 | 約 0.5 秒 | 3.3–3.4 秒 |
| 第 1 次耗時 | 約 1 秒 | 約 1 秒 | 11.9 秒 |
| 系統記憶體峰值 | 未測 | 未測 | 2268MB |
| VRAM | 不使用 | 不使用 | 約增加 3.3GB |

其他實測：

- dxcam 截圖 8–11ms，能截到無邊框模式的遊戲畫面。
- RapidOCR v5 搭配 eslav 模型：俄文全對，英文有 Joumal 錯字；只涵蓋俄、白俄、烏克蘭、英文。
- Surya（GPU）在遊戲進行中：熱機後 4.6–4.8 秒，第 1 次 23.4 秒，記憶體峰值 2397MB，VRAM 已用由 10287MB 增至 11226MB，辨識結果與未開遊戲時相同；該遊戲於辨識期間未受影響。
- Surya 在 CPU（llama.cpp CPU 版）：熱機後 15.9–17.7 秒，記憶體峰值 3589MB，辨識結果與 GPU 版相同。
- RapidOCR 依文字行高度排序輸出，全畫面時左右欄同高度的文字會交錯；Surya 依區塊輸出，同區塊多行合為一段。
- 同一行俄文 КАРТОФЕЛИНА：v6 輸出錯誤結果 KAPTOENHA，信心分數 0.94；v5 eslav 輸出正確結果，信心分數 0.89。
- Surya 結束時的 llama-server 清理步驟停住不結束。

## 待辦

- 原型提交到 prototype/ocr-bench 分支。
- 進入主線步驟 3 to-spec。

## 未決

- 預設使用的 Ollama 模型。
- 日文 OCR 尚未實測。
- 繁體中文在 Surya 的辨識品質尚未實測。
- 全畫面 OCR 結果送翻譯前的區塊分組方式。
- Surya 結束時 llama-server 清理停住的處理方式。
