# 玩家沉浸式翻譯工具，Gamer Immersive Translator

## 簡介 / Introduction

Gamersive-Translate 是 Windows 上的遊戲內翻譯工具。平時收在螢幕右緣，需要時展開面板，翻譯輸入的文字或擷取遊戲畫面辨識後翻譯。

Gamersive-Translate is an in-game translation tool for Windows. It stays at the right edge of the screen and opens a panel when needed to translate typed text or recognize and translate text captured from the game screen.

## 功能 / Features

- 邊條與面板：滑鼠停在螢幕右緣的邊條上，或用 Alt+Tab 切到本程式，即展開面板；點其他視窗、Alt+Tab 切走或按 Esc 收合。
  Strip and panel: hover over the strip at the right edge of the screen, or Alt+Tab to the app, to open the panel; click another window, Alt+Tab away, or press Esc to close it.
- 文字翻譯頁：輸入原文，按 Enter 翻譯。
  Text page: type the source text and press Enter to translate.
- OCR 頁：擷取全畫面、上半部、下半部、九宮格選取的格子或自訂框選的範圍，辨識文字後自動翻譯。
  OCR page: capture the full screen, the top or bottom half, selected cells of a 3×3 grid, or a custom selection; the recognized text is translated automatically.
- 拼音：翻譯後在原文下方顯示原文的拉丁字母拼音。
  Romanization: after translation, the Latin-alphabet romanization of the source text is shown below it.
- 翻譯引擎：Google Cloud Translation、OpenAI 相容 API、Ollama。
  Translation engines: Google Cloud Translation, OpenAI-compatible APIs, and Ollama.
- 支援無邊框視窗與視窗化的遊戲。
  Supports games in borderless windowed and windowed mode.

## 系統需求 / Requirements

- 開發與測試環境：Windows 11 Home 25H2、Python 3.10.11。
  Developed and tested on Windows 11 Home 25H2 with Python 3.10.11.
- OCR 主引擎 Surya 需要 NVIDIA GPU 與 CUDA，並需要以下檔案；無法使用時改用 CPU 的 RapidOCR。
  The main OCR engine, Surya, requires an NVIDIA GPU with CUDA and the files below; when it is unavailable, the CPU-based RapidOCR is used.
  - 專案根目錄的 `llama.cpp-cuda/`：llama.cpp b11669 CUDA 12.4 版 `llama-server.exe`。
    `llama.cpp-cuda/` in the project root: `llama-server.exe` from llama.cpp b11669, CUDA 12.4 build.
  - Hugging Face 本機快取中的 `datalab-to/surya-ocr-2.5-gguf`（`surya-2.5.gguf`、`surya-2.5-mmproj.gguf`）。
    `datalab-to/surya-ocr-2.5-gguf` (`surya-2.5.gguf`, `surya-2.5-mmproj.gguf`) in the local Hugging Face cache.

## 安裝與啟動 / Installation and Running

在專案根目錄的虛擬環境 `.venv` 中（PowerShell）：
In the virtual environment `.venv` in the project root (PowerShell):

| 動作 / Action | 指令 / Command |
|---|---|
| 安裝套件 / Install packages | `.venv\Scripts\python -m pip install -r requirements.txt` |
| 啟動 / Run | `.venv\Scripts\python -m gt` |
| 測試 / Test | `.venv\Scripts\python -m pytest` |
| 結束 / Quit | 終端機按 Ctrl+C / Press Ctrl+C in the terminal |

## 設定 / Configuration

設定存在 `%LOCALAPPDATA%\Gamersive-Translate\config.json`，在面板的「設定」頁修改。
Settings are stored in `%LOCALAPPDATA%\Gamersive-Translate\config.json` and are changed on the panel's Settings tab.

| 翻譯引擎 / Engine | 設定欄位 / Fields |
|---|---|
| Google | API key |
| OpenAI 相容 / OpenAI-compatible | base URL、API key、model |
| Ollama | endpoint、model |

設定頁另可選擇螢幕、開關動畫、選擇字型與大小。
The Settings tab also lets you choose the screen, turn animations on or off, and pick the font and size.

## 使用方式 / Usage

1. 啟動後，滑鼠停在螢幕右緣的邊條上，或用 Alt+Tab 切到「Gamersive-Translate」，展開面板。
   After starting, hover over the strip at the right edge of the screen, or Alt+Tab to "Gamersive-Translate", to open the panel.
2. 文字翻譯頁：輸入原文，按 Enter 或「翻譯」；Shift+Enter 換行；「清除」清空這一頁。
   Text page: type the source text and press Enter or "翻譯" (Translate); Shift+Enter inserts a new line; "清除" (Clear) empties the page.
3. OCR 頁：選擇截圖區域或九宮格後按「截圖」，或按「自訂框選」拖出範圍後按 ✓；辨識出的原文可修改後按 Enter 重新翻譯。
   OCR page: choose a capture region or grid cells and press "截圖" (Capture), or press "自訂框選" (Custom Selection), drag a box, and press ✓; the recognized text can be edited and translated again with Enter.
4. 原文框與譯文框右下角：🔊 聆聽、⧉ 複製、🔍 Google 搜索。
   Bottom-right of the source and translation boxes: 🔊 listen, ⧉ copy, 🔍 Google search.

## 專案文件 / Project Documentation

完整規格、開發流程與進度：[project.md](project.md)
Full specification, development workflow, and progress: [project.md](project.md)

## 授權 / License

保留所有權利（All rights reserved）。
