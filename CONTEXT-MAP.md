# Gamersive-Translate 工作地圖

```
Gamersive-Translate/
│
├── README.md              ← GitHub 首頁說明（簡介、功能、安裝、設定、使用）
├── project.md             ← 專案文件（專案資訊、進度、實作規則、開發環境、產品規格、待辦、未決）
├── CONTEXT-MAP.md         ← 本地圖
├── AGENTS.md              ← agent skill 設定（issue tracker、domain docs）
├── GLOSSARY.md            ← 領域詞彙
├── requirements.txt       ← Python 套件
├── pytest.ini             ← pytest 設定
├── .gitignore             ← 排除 .scratch/、__pycache__/、.pytest_cache/、.venv/、llama.cpp-cuda/
│
├── .venv/                 ← 虛擬環境
├── .scratch/GT/           ← spec.md（issue #1 規格）、issues/01.md–07.md、roman*.png 7 張
├── gt/                    ← 程式本體（python -m gt）
├── tests/                 ← pytest 測試；fixtures/ 放 game-en-ru.png
├── llama.cpp-cuda/        ← llama-server.exe 與 CUDA DLL（Surya 用）
├── prototype/             ← 未加入 git；原型程式在 prototype/ocr-bench 分支
│   ├── .venv/、.venv-surya/  ← Python 3.10.11 虛擬環境
│   ├── llama.cpp/         ← llama.cpp 執行檔（有 llama-server.exe，沒有 ggml-cuda.dll）
│   └── __pycache__/       ← PROTOTYPE-memwatch.cpython-310.pyc
└── docs/
    ├── adr/               ← 架構決策紀錄（0001-pyside6-gui.md）
    └── agents/
        ├── domain.md          ← skill 讀 GLOSSARY.md 與 docs/adr/ 的方式
        ├── flow-status.md     ← sevid-flow 主線步驟狀態
        └── issue-tracker.md   ← GitHub Issues 的 gh 操作慣例
```

## GitHub（SevidLim/Gamersive-Translate）

| 項目 | 內容 |
|---|---|
| 規格 | issue #1「GT 規格：遊戲內翻譯工具」 |
| 實作票 | #1 的子 issue：#2 邊條與面板開合、#3 Alt+Tab 展開與焦點、#4 文字翻譯頁 + Google 翻譯、#5 OpenAI 相容與 Ollama 引擎、#6 OCR 頁（RapidOCR）、#7 Surya 主引擎與備用切換、#8 設定：螢幕、動畫、全螢幕提示 |
| 票的相依 | #3、#4、#8 等 #2；#5、#6 等 #4；#7 等 #6 |
| 原型分支 | prototype/ocr-bench |

## Skill

| 項目 | 內容 |
|---|---|
| 開發流程 | sevid-flow 主線 skill 組 |
| 實作 sub agent | implement、tdd |
| 派工前要讀 | 票、規格、GLOSSARY.md |
