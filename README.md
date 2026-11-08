# Gamersive-Translate

Windows 遊戲內翻譯工具。平時收在螢幕右緣，需要時展開面板翻譯文字或遊戲畫面，不打斷遊玩。

## 專案資訊

| 項目 | 內容 |
|---|---|
| 位置 | Claude Agents/projects/Gamersive-Translate |
| GitHub | SevidLim/Gamersive-Translate（公開），remote 為 origin |
| 規格 | GitHub issue #1「GT 規格：遊戲內翻譯工具」 |
| 實作票 | #1 的子 issue：#2 邊條與面板開合、#3 Alt+Tab 展開與焦點、#4 文字翻譯頁 + Google 翻譯、#5 OpenAI 相容與 Ollama 引擎、#6 OCR 頁（RapidOCR）、#7 Surya 主引擎與備用切換、#8 設定：螢幕、動畫、全螢幕提示 |
| 票的相依 | #3、#4、#8 等 #2；#5、#6 等 #4；#7 等 #6 |
| 分支 | master；原型在 prototype/ocr-bench |
| 開發流程 | sevid-flow 主線 skill 組 |
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
| 3 | 規格（to-spec） | done |
| 4 | 拆票（to-tickets） | done |
| 5 | 實作 | doing（#2、#3、#4、#5、#6 done） |
| 6 | PR | todo |
| 7 | 回顧 | todo |

步驟 2 的 handoff 不執行。

步驟 5 實作規則：

- 全部票在同一個對話進行，依票的相依順序逐張實作。
- 每張票交給一個 sub agent 實作（sub agent 讀 implement、tdd skill）。
- sub agent 只寫檔；git 提交由使用者在 Windows 執行。
- 實作直接在 master 分支進行。
- 每張票的收尾順序：
  1. sub agent 回報。
  2. 主對話讀程式碼、重跑測試，確認與驗證。
  3. 主對話列出使用者手動測試清單：執行指令、逐步操作、每步預期結果、需貼回的輸出（log、指令輸出、截圖）。
  4. 使用者測試回報；有問題修正後回到第 2 步。
  5. 主對話列出提交指令（commit 訊息含 `Closes #<票號>`），使用者執行。
  6. code-review：Standards 與 Spec 兩個 sub agent 平行執行，比對基準為該票開始前的 commit；主對話核對結果，需修正者修正後回到第 5 步。
  7. project-update。
- 對話用量達 60 萬 tokens 時：確認目前用量，判斷能否再完成一張票；不能則執行 project-update，並產出新對話開場指示（要讀的規範與專案檔清單、下一張票號與後續順序、本節步驟 5 實作規則）。
- 用量來源：使用者每則訊息末尾的 `[usage-band]` 用量行。

## 開發環境

| 項目 | 內容 |
|---|---|
| 作業系統 | Windows 11 Home 25H2（build 26200.7840） |
| 顯示卡 | NVIDIA GeForce RTX 4070，12GB VRAM，驅動 595.79，最高支援 CUDA 13.2 |
| 螢幕 | 主螢幕 2560x1440 |
| Python | 3.10.11 |
| git | 2.49.0.windows.1 |
| gh CLI | 2.103.3，已登入 SevidLim（keyring，https，scope：gist、read:org、repo、workflow） |
| 專案虛擬環境 | 專案根目錄 .venv，套件依 requirements.txt：PySide6 6.12.0、pytest 9.2.0、dxcam 0.3.0、rapidocr 3.10.0、onnxruntime 1.23.2、opencv-python-headless 5.0.0.93、numpy 2.2.6 |

執行方式（PowerShell，於專案根目錄）：

| 動作 | 指令 |
|---|---|
| 啟動 | .venv\Scripts\python -m gt |
| 安裝套件 | .venv\Scripts\python -m pip install -r requirements.txt |
| 測試 | .venv\Scripts\python -m pytest |
| 結束 | 終端機按 Ctrl+C |
| 讀 debug log | Get-Content -Encoding UTF8 "$env:LOCALAPPDATA\Gamersive-Translate\debug.log" |

## 產品規格

### 技術選型

| 項目 | 決定 |
|---|---|
| GUI 框架 | PySide6，沿用 Desktop-Agent-Pet 的 src/glass.py（Acrylic 毛玻璃、置頂無邊框視窗、側滑動畫） |
| 視覺語彙 | 半透明毛玻璃與按鍵設計，規格見本文件「視覺規格」，以 QSS 實作 |
| 截圖 | dxcam（DXGI Desktop Duplication），擷取主螢幕 |
| OCR 主引擎 | Surya（surya-ocr 0.23.0）：文字偵測以 torch 在 CPU 執行；辨識由 llama.cpp b11669 CUDA 12.4 版 llama-server 在 GPU 執行，模型 surya-2.5.gguf 與 surya-2.5-mmproj.gguf |
| OCR 備用引擎 | RapidOCR 3.10.0（ONNX Runtime CPU）：PP-OCRv6 small、PP-OCRv5 mobile |
| 設定檔 | %LOCALAPPDATA%\Gamersive-Translate\config.json，API key 一併存放 |

### 視覺規格

材質：所有浮層為半透明底加背景模糊。

| 層級 | 底色基準 | 模糊 |
|---|---|---|
| 主要控制項（搜尋框、磚塊 hover） | `--panel` | 14–20px |
| 浮出面板（資料夾、新增視窗） | `--panel` | 26px |
| 深色浮層（emoji 選單、目標選單、確認面板） | 固定深灰 0.80–0.93 | 16–22px |

- 浮層疊在浮層上時，上層用固定深色，不跟隨主題變數，層次靠明度差拉開。

色彩：

- 前景色由桌布平均亮度決定，寫入 `--text`，並以 `data-ink` 切換面板底色的明暗方向。
- 刪除確認面板與各類深色浮層固定深底白字，不隨 `data-ink` 變動。

圓角：

| 尺度 | 用途 |
|---|---|
| 999px | 膠囊：搜尋框、切換鈕、按鈕、dock 面板 |
| 16–18px | 面板與磚塊 |
| 10–12px | 輸入欄位、選單項目 |
| 50% | 圓形按鈕與圖示底 |

尺寸：所有重複出現的尺寸集中為 CSS 變數，不散落魔術數字。

| 變數 | 用途 |
|---|---|
| `--dock-btn` `--dock-w` | 右下面板 |
| `--add-row` `--add-ctl` | 新增視窗欄位與控制項 |
| `--radius` | 面板圓角 |

- 同一列的控制項高度必須相等，靠變數鎖定而非個別調整 padding。

動畫時長：

| 動作 | 時長 |
|---|---|
| 浮層展開 | 200–220ms |
| 浮層收合 | 140–160ms |
| 位移與讓位 | 160–200ms |
| 微互動（hover、色彩） | 120–160ms |

- 從觸發點長出來：變形原點對準觸發元素中心。
- 只動該動的：未受影響的元素保持靜止。
- 收合一律比展開快。
- 展開與收合成對，收合播完才隱藏。
- 可中斷：動畫保留 handle，重複觸發時取消前一次。
- 動畫可整體關閉：關閉時所有 duration 與 delay 歸零，JS 端跳過 `Element.animate()` 並改為立即切換狀態。
- 新功能加入動畫時必須同時處理關閉路徑。

緩動曲線：

| 情境 | 曲線 |
|---|---|
| 進場 | cubic-bezier(0.16, 1, 0.3, 1) |
| 位移 | cubic-bezier(0.2, 0.9, 0.3, 1) |
| 退場 | ease-in 或 cubic-bezier(0.4, 0, 0.9, 0.35) |

### 支援的遊戲顯示模式

- 支援無邊框視窗化與視窗化。
- 遇到獨佔全螢幕時，面板提示改用無邊框模式。

### 邊條與面板

- 收合時螢幕右緣露出邊條：寬 6px、高 120px、垂直置中、半透明。
- 面板尺寸 420x640，垂直置中，Acrylic 毛玻璃上疊深灰 tint，不透明度 0.30。
- 滑鼠停在邊條展開面板：從進入邊條到完全展開共 1.5 秒（停留 1290ms ＋ 展開動畫 210ms）。
- Alt+Tab 切到本程式時自動展開面板。
- 滑鼠停留展開與 Alt+Tab 展開後，焦點都進入文字翻譯頁的輸入框，不自動截圖。
- 面板收合：點其他視窗、Alt+Tab 切走、按 Esc。
- 面板展開期間以前景切換事件判斷失去焦點；前景切到 Alt+Tab 過渡視窗（class ForegroundStaging、XamlExplorerHostIslandWindow）不視為失去焦點。
- Alt+Tab 清單中的「Gamersive-Translate」為一個 1x1、位於所有螢幕範圍外的主視窗；面板取得前景後隱藏主視窗，面板收合後以不啟用方式重新顯示。
- 程式啟動時與每次面板收合後，主視窗短暫取得前景再交還原本的 app；交接期間不觸發展開與收合。
- 「Gamersive-Translate」在 Alt+Tab 清單排第二。
- 工作列有「Gamersive-Translate」按鈕，面板展開期間消失。
- 面板預設貼主螢幕右緣，設定中可切換螢幕。

### 文字翻譯頁

- 上下分屏：上方輸入原文，下方顯示譯文（唯讀）；中間一列為語言標示「自動偵測 → 繁體中文」與膠囊形翻譯按鈕。
- 來源語言預設自動偵測，目標語言預設繁體中文（config.json：source_lang "auto"、target_lang "zh-TW"）。
- 按 Enter 或翻譯按鈕送出，Shift+Enter 換行。
- 翻譯在背景執行，進行中翻譯按鈕停用。
- 翻譯失敗時原文保留，面板底部以紅底訊息顯示 4 秒。
- 面板下方為翻譯引擎下拉選單（Google、OpenAI 相容、Ollama），下拉選單下方只顯示所選引擎的設定欄位；切換時寫入 config.json 的 engine。
- 設定欄位按 Enter 或離開欄位時寫入 config.json：

| 引擎 | 欄位（placeholder） | config.json 鍵 |
|---|---|---|
| Google | Google API key（遮罩） | google_api_key |
| OpenAI 相容 | base URL、API key（遮罩）、model | openai_base_url、openai_api_key、openai_model |
| Ollama | endpoint（預設 http://localhost:11434）、model | ollama_endpoint、ollama_model |

- 設定欄位 placeholder 為英文，其他介面文字為中文。
- 下拉選單的選項清單為不透明深色底。
- 輸入欄位圓角 11px、半透明底；按鈕膠囊形，圓角半徑為按鈕高度的一半。

### OCR 頁

- OCR 頁的辨識由 RapidOCR（預設參數 PP-OCRv6 small）執行，第一次辨識時載入模型；Surya 主引擎與備用切換由 #7 實作。
- 面板上方有「文字翻譯」「OCR」兩個膠囊分頁鈕；面板展開時與 Alt+Tab 切回時切到文字翻譯頁並聚焦輸入框。
- 截圖選項一行，由左到右：截圖區域下拉清單（全畫面、上半部、下半部，預設全畫面）、「九宮格」按鈕、「截圖」按鈕。
- 按「九宮格」在按鈕右側展開九宮格浮出面板：3x3 相連方格，點格切換選取，選取格為較亮底；點面板外或再點「九宮格」收合；選取保留。
- 有選九宮格時截取所選格子的外框矩形；九宮格未選時截取下拉清單的區域；在下拉清單選區域時清空九宮格選取。
- 按「截圖」：面板立即隱藏，60ms 後截圖，面板立即顯示並取回前景；隱藏與顯示回來後 500ms 內面板不收合。截圖與辨識進行中「截圖」鈕停用。
- 截圖 2 秒內未取得畫面時重置截圖並顯示「OCR 失敗：截圖逾時」；截圖或辨識失敗以「OCR 失敗：{原因}」紅底訊息顯示 4 秒。
- 辨識結果一行一個文字區塊，依 RapidOCR 輸出順序以換行串成原文，填入上方原文框並自動翻譯；下方為譯文。
- 原文可修改，按 Enter 或翻譯鈕重新翻譯，Shift+Enter 換行。
- 兩頁一次只翻一筆：翻譯進行中兩頁翻譯鈕停用；辨識完成時若有翻譯進行中，該筆回來後自動送出 OCR 翻譯。
- 畫面上出現任何語言都要自動辨識正確，使用者不手動選語言或換模型。

### 翻譯引擎

| 引擎 | 接法 |
|---|---|
| Google（預設） | Cloud Translation Basic（v2），API key 認證，key 以網址參數傳送並經網址編碼，format=text，不帶來源語言即自動偵測；每月前 50 萬字元免費 |
| OpenAI 相容 | POST {base URL}/chat/completions，一律帶 Authorization: Bearer {API key}（key 空時送空值），譯文取 choices[0].message.content，錯誤訊息取 error.message；可接 Claude、Gemini、OpenRouter 等 |
| Ollama | POST {endpoint}/api/chat，stream 為 false，譯文取 message.content，錯誤訊息取 error |

- 第一次啟動預設 Google（config.json engine "google"）。
- Google 在文字翻譯頁整段送出一個 q；在 OCR 頁每個非空行一個 q，每 128 行送一次請求，譯文依原順序以換行串回，任一次失敗即顯示該次失敗訊息。OpenAI 相容與 Ollama 兩頁都整段送出。
- OpenAI 相容與 Ollama 的提示：system 訊息「把使用者的文字翻成 {目標語言代碼}，只輸出譯文。」，user 訊息為原文。
- 程式內有語言代碼對照表 zh-TW → 繁體中文；提示使用語言代碼。
- 未送出請求即失敗的情況：Google 未設定 API key（「未設定 API key」）；OpenAI 相容未設定 model（「未設定模型」）；Ollama 未設定 endpoint（「未設定端點」）、未設定 model（「未設定模型」）。
- 失敗訊息格式：「{引擎} 翻譯失敗：{原因}」；原因為連線失敗、請求失敗、HTTP {狀態碼}：{伺服器訊息}、HTTP {狀態碼}、回應格式無法解析，或上列未設定訊息。
- 翻譯失敗時不自動換引擎重試。

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
| OCR 引擎 | 輸入圖片、輸出依閱讀順序排列的文字區塊的辨識服務，目前實作 RapidOCR | |
| 文字區塊 | OCR 引擎輸出的一段文字；RapidOCR 為一行一個區塊 | |
| 翻譯引擎（engine） | 把原文翻成譯文的服務，可選 Google、OpenAI 相容或 Ollama | 翻譯器、後端 |
| Google | 使用 Google Cloud Translation（Basic v2）的翻譯引擎，以 API key 認證 | |
| OpenAI 相容（OpenAI-compatible） | 使用 OpenAI Chat Completions 格式 API 的翻譯引擎 | |
| Ollama | 使用本機 Ollama 服務 /api/chat 的翻譯引擎 | |
| base URL | OpenAI 相容引擎的 API 根網址，請求送到 {base URL}/chat/completions | |
| API key（金鑰） | 翻譯引擎用來認證的金鑰；Google 放在網址參數，OpenAI 相容以 Bearer 標頭送出 | token |
| 模型（model） | OpenAI 相容與 Ollama 引擎用來翻譯的模型名稱 | |
| 端點（endpoint） | Ollama 的服務網址，預設 http://localhost:11434 | |

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

- 主線步驟 5 實作：下一張 #7，之後 #8。

## 未決

- 預設使用的 Ollama 模型。
- 日文 OCR 尚未實測。
- 繁體中文在 Surya 的辨識品質尚未實測。
- 全畫面 OCR 結果送翻譯前的區塊分組方式。
- Surya 結束時 llama-server 清理停住的處理方式。
- config.json 內容損毀時的啟動方式。
- Acrylic 開啟失敗時，不透明底的圓角裁切。
- 偶發的面板不透明底（Acrylic 回報成功時）的原因；debug.log 保留 acrylic 結果紀錄。
