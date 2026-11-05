# GUI 框架採用 PySide6

面板需要 Windows 原生毛玻璃（Acrylic）、置頂無邊框視窗與側滑動畫。Desktop-Agent-Pet 的 `src/glass.py` 已用 PySide6 實作這三項，且 OCR 引擎候選都有 Python 介面，因此選 PySide6 並沿用該實作。代價是 Quiet Tab 的 CSS 需改寫成 QSS。

## Considered Options

- Electron：可直接沿用 Quiet Tab CSS；原生毛玻璃 `setBackgroundMaterial` 需 Windows 11 22H2 以上。
- Tauri v2：可直接沿用 Quiet Tab CSS；`Acrylic` 支援 Windows 10/11，後端為 Rust。
- CSS `backdrop-filter` 只模糊視窗自身內容，無法模糊後方遊戲畫面，故三者都必須走系統原生材質。
