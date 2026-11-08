"""邊條與面板的 Qt 視窗。開合時機全由面板狀態機決定，這裡只負責畫面與動畫。

面板的毛玻璃做法沿用 Desktop-Agent-Pet 的 src/glass.py：
不設 WA_TranslucentBackground，由 Windows Acrylic 畫模糊；失敗時畫不透明深色底。
側滑也照 glass.py：視窗寬度從 0 變到全寬，內容固定全寬、靠左貼齊，看起來是滑出來。
"""

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from gt import debuglog, platform_win
from gt.translate import ENGINES

# 視覺規格（README「視覺規格」）
STRIP_W = 6
STRIP_H = 120
STRIP_COLOR = QColor(255, 255, 255, 90)          # 半透明（≈0.35）
PANEL_W = 420
PANEL_H = 640
PANEL_RADIUS = 16                                # 面板圓角 16–18px
PANEL_BG = QColor(20, 20, 26)                    # Acrylic 失敗時的不透明底
PANEL_STROKE = QColor(255, 255, 255, 41)         # 細白邊（≈0.16）
ACRYLIC_TINT = "14141A4D"                        # 深灰 0.30，疊在模糊上
EXPAND_MS = 210                                  # 浮層展開 200–220ms
COLLAPSE_MS = 150                                # 浮層收合 140–160ms
FIELD_RADIUS = 11                                # 輸入欄位 10–12px
CTL_H = 32                                       # 同一列控制項等高
FIELD_PAD_X = 8                                  # 輸入欄位與下拉框左右內距
STATUS_MS = 4000                                 # 失敗訊息顯示多久
CELL_SIZE = CTL_H                                # 九宮格面板每格邊長
POPUP_BG = QColor(32, 32, 40, 204)               # 深色浮層固定深灰 0.80，與下拉清單選項清單相同
GRID_LINE = QColor(255, 255, 255, 51)            # 九宮格外框與格線（≈0.20）
CELL_SELECTED = QColor(255, 255, 255, 87)        # 選取格的較亮半透明底（≈0.34）

# 文字翻譯頁的 QSS（README「視覺規格」：半透明底、輸入欄位圓角、按鈕膠囊）
PAGE_QSS = f"""
QLabel {{ color: #f2f2f5; background: transparent; }}
QPlainTextEdit, QLineEdit {{
    color: #f2f2f5; background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.16); border-radius: {FIELD_RADIUS}px;
    padding: 6px {FIELD_PAD_X}px; selection-background-color: rgba(255, 255, 255, 0.30);
}}
QPlainTextEdit:focus, QLineEdit:focus {{ border-color: rgba(255, 255, 255, 0.40); }}
QLineEdit {{ min-height: {CTL_H - 14}px; max-height: {CTL_H - 14}px; }}
QComboBox {{
    color: #f2f2f5; background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.16); border-radius: {FIELD_RADIUS}px;
    padding: 0 {FIELD_PAD_X}px; min-height: {CTL_H - 2}px; max-height: {CTL_H - 2}px;
}}
QComboBox QAbstractItemView {{ color: #f2f2f5; background: rgba(32, 32, 40, 0.80); }}
QPushButton {{
    color: #f2f2f5; background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.20); border-radius: {CTL_H // 2 - 1}px;  /* 膠囊：半徑＝按鈕高的一半 */
    min-height: {CTL_H - 2}px; max-height: {CTL_H - 2}px; padding: 0 16px;
}}
QPushButton:hover {{ background: rgba(255, 255, 255, 0.22); }}
QPushButton:checked {{ background: rgba(255, 255, 255, 0.34); border-color: rgba(255, 255, 255, 0.50); }}  /* 切換鈕選取狀態 */
QPushButton:disabled {{ color: rgba(242, 242, 245, 0.45); }}
QLabel#status {{
    color: #ffd7d7; background: rgba(120, 20, 20, 0.55);
    border-radius: {FIELD_RADIUS}px; padding: 6px 10px;
}}
"""


def bezier(x1, y1, x2, y2):
    c = QEasingCurve(QEasingCurve.BezierSpline)
    c.addCubicBezierSegment(QPointF(x1, y1), QPointF(x2, y2), QPointF(1, 1))
    return c


EXPAND_CURVE = bezier(0.16, 1, 0.3, 1)           # 進場
COLLAPSE_CURVE = bezier(0.4, 0, 0.9, 0.35)       # 退場

TOP_FLAGS = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint


class Strip(QWidget):
    """邊條：貼主螢幕右緣、垂直置中。"""

    entered = Signal()
    left = Signal()

    def __init__(self, screen):
        super().__init__(None, TOP_FLAGS)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        g = screen.geometry()
        self.setGeometry(g.x() + g.width() - STRIP_W, g.y() + (g.height() - STRIP_H) // 2, STRIP_W, STRIP_H)

    def enterEvent(self, e):
        super().enterEvent(e)
        self.entered.emit()

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self.left.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(STRIP_COLOR)
        p.drawRoundedRect(QRectF(self.rect()), STRIP_W / 2, STRIP_W / 2)


class HostWindow(QWidget):
    """供 Alt+Tab 選取的主視窗：非 Tool、可見，放在所有螢幕範圍之外，使用者看不到。
    邊條與面板是 Tool 視窗，不會列入 Alt+Tab 清單。
    面板取得前景後隱藏 host（隱藏的視窗不列入 Alt+Tab 清單），面板收合後再以不啟用的方式顯示。"""

    activated = Signal()
    deactivated = Signal()

    def __init__(self, screen):
        super().__init__(None)
        self.setWindowTitle("Gamersive-Translate")
        v = screen.virtualGeometry()                # 所有螢幕的聯集
        self.setGeometry(v.x() - 1000, v.y(), 1, 1)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # 重新顯示時不搶前景、不觸發 activated

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.activated.emit()
        if e.type() == QEvent.ActivationChange and not self.isActiveWindow():
            self.deactivated.emit()


class SourceEdit(QPlainTextEdit):
    """原文輸入框：Enter 送出，Shift+Enter 換行。"""

    submitted = Signal()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not e.modifiers() & Qt.ShiftModifier:
            self.submitted.emit()
            return
        super().keyPressEvent(e)


class GridPopup(QWidget):
    """九宮格浮出面板：Qt.Popup，點面板外自動收合；3x3 相連方格，點一格切換選取。"""

    def __init__(self, parent):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(3 * CELL_SIZE + 1, 3 * CELL_SIZE + 1)
        self.cells = set()                              # 選取的格號 1–9，左上到右下
        self.closed_by_button = False                   # 這次收合是點九宮格按鈕造成的

    def clear(self):
        self.cells.clear()
        self.update()

    def mousePressEvent(self, e):
        if not self.rect().contains(e.position().toPoint()):
            button = self.parentWidget()
            self.closed_by_button = button.rect().contains(button.mapFromGlobal(e.globalPosition().toPoint()))
            super().mousePressEvent(e)                  # 點到面板外：交給 QWidget 預設處理，收合 popup
            return
        col, row = int(e.position().x()) // CELL_SIZE, int(e.position().y()) // CELL_SIZE
        if 0 <= col < 3 and 0 <= row < 3:
            self.cells ^= {row * 3 + col + 1}
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), POPUP_BG)
        for n in self.cells:
            p.fillRect((n - 1) % 3 * CELL_SIZE, (n - 1) // 3 * CELL_SIZE, CELL_SIZE, CELL_SIZE, CELL_SELECTED)
        p.setPen(QPen(GRID_LINE, 1))
        for i in range(4):                              # 外框與格線相連
            p.drawLine(i * CELL_SIZE, 0, i * CELL_SIZE, 3 * CELL_SIZE)
            p.drawLine(0, i * CELL_SIZE, 3 * CELL_SIZE, i * CELL_SIZE)


class Panel(QWidget):
    """面板：從主螢幕右緣滑出的毛玻璃視窗，內含文字翻譯頁的輸入框。"""

    esc_pressed = Signal()
    activated = Signal()
    focus_lost = Signal()
    animation_done = Signal()
    translate_requested = Signal(str, bool)      # 原文、是否一行一個文字區塊（OCR 頁）
    capture_requested = Signal(str, object)      # 截圖區域、九宮格格號集合
    setting_changed = Signal(str, str)           # config 欄位名、值

    def __init__(self, screen, cfg):
        super().__init__(None, TOP_FLAGS)
        self.screen_geo = screen.geometry()
        self.use_acrylic = platform_win.IS_WIN
        if not self.use_acrylic:
            self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("glassPanel")             # 照 glass.py：視窗底透明，模糊由系統畫
        self.setStyleSheet("QWidget#glassPanel { background: transparent; }")
        self.acrylic = False
        self._acrylic_tried = False
        self.inner = QWidget(self)                      # 固定全寬、靠左，視窗變寬時露出來
        self.inner.setGeometry(0, 0, PANEL_W, PANEL_H)
        box = QVBoxLayout(self.inner)
        title = QLabel("Gamersive-Translate")
        title.setStyleSheet("color: #f2f2f5; font-size: 12pt; font-weight: 600; background: transparent;")
        box.addWidget(title, 0, Qt.AlignTop | Qt.AlignHCenter)
        self.inner.setStyleSheet(PAGE_QSS)
        self.tabs = [QPushButton("文字翻譯"), QPushButton("OCR")]
        tab_row = QHBoxLayout()
        for i, b in enumerate(self.tabs):
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, i=i: self._select_tab(i))
            tab_row.addWidget(b)
        tab_row.addStretch(1)
        self.stack = QStackedWidget()
        text_page = QWidget()
        text_box = QVBoxLayout(text_page)
        text_box.setContentsMargins(0, 0, 0, 0)
        langs = QLabel("自動偵測 → 繁體中文")
        self.input = SourceEdit()                       # 文字翻譯頁上方：原文
        self.input.setPlaceholderText("輸入原文，Enter 翻譯，Shift+Enter 換行")
        self.translate_btn = QPushButton("翻譯")
        row = QHBoxLayout()
        row.addWidget(langs, 1)
        row.addWidget(self.translate_btn)
        self.output = QPlainTextEdit()                  # 文字翻譯頁下方：譯文
        self.output.setReadOnly(True)
        self.output.setFocusPolicy(Qt.ClickFocus)
        text_box.addWidget(self.input, 1)
        text_box.addLayout(row)
        text_box.addWidget(self.output, 1)
        self.stack.addWidget(text_page)
        self.stack.addWidget(self._build_ocr_page())
        self._select_tab(0)
        self.engine_box = QComboBox()                   # 最小設定入口：引擎與其欄位（完整設定頁屬 #8）
        for key, engine in ENGINES.items():
            self.engine_box.addItem(engine.name, key)
        self.engine_rows = {}
        settings = QVBoxLayout()
        settings.addWidget(self.engine_box)
        for key, engine in ENGINES.items():
            w = QWidget()
            col = QVBoxLayout(w)
            col.setContentsMargins(0, 0, 0, 0)
            for field in engine.fields:
                edit = QLineEdit(cfg[field.config_key])
                edit.setPlaceholderText(field.placeholder)
                if field.secret:
                    edit.setEchoMode(QLineEdit.Password)
                edit.editingFinished.connect(lambda f=field.config_key, e=edit: self.setting_changed.emit(f, e.text().strip()))
                col.addWidget(edit)
            self.engine_rows[key] = w
            settings.addWidget(w)
        self.engine_box.setCurrentIndex(max(0, self.engine_box.findData(cfg["engine"])))
        self.engine_box.currentIndexChanged.connect(self._engine_selected)
        self._show_engine_fields()
        self.status = QLabel()                          # 面板底部的短暫失敗訊息
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.status.hide()
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(STATUS_MS)
        self._status_timer.timeout.connect(self.status.hide)
        box.addLayout(tab_row)
        box.addWidget(self.stack, 1)
        box.addLayout(settings)
        box.addWidget(self.status)
        self.input.submitted.connect(lambda: self._submit(self.input, self.output, False))
        self.translate_btn.clicked.connect(lambda: self._submit(self.input, self.output, False))
        self.ocr_input.submitted.connect(lambda: self._submit(self.ocr_input, self.ocr_output, True))
        self.ocr_translate_btn.clicked.connect(lambda: self._submit(self.ocr_input, self.ocr_output, True))
        self.capture_btn.clicked.connect(self._capture)
        self._target_output = self.output                # 翻譯結果要顯示的譯文框
        self._ocr_pending = False                       # 辨識完成時有翻譯進行中，OCR 翻譯待送出
        self.setFocusPolicy(Qt.StrongFocus)
        self._width = 0
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._step)
        self._anim.finished.connect(self.animation_done)
        self._ensure_acrylic()                          # 啟動時先套 Acrylic，第一次展開不再等待

    def _build_ocr_page(self):
        """OCR 頁：截圖區域選擇列、截圖按鈕；上方原文（可修改後重新翻譯），下方譯文。"""
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        region_row = QHBoxLayout()
        self.region_box = QComboBox()                   # 截圖區域，預設全畫面
        for key, label in (("full", "全畫面"), ("top", "上半部"), ("bottom", "下半部")):
            self.region_box.addItem(label, key)
        self.region_box.activated.connect(lambda _: self._select_region())
        self.grid_btn = QPushButton("九宮格")
        self.grid_popup = GridPopup(self.grid_btn)
        self.grid_btn.clicked.connect(self._open_grid)
        self.capture_btn = QPushButton("截圖")
        region_row.addWidget(self.region_box)
        region_row.addWidget(self.grid_btn)
        region_row.addWidget(self.capture_btn)
        region_row.addStretch(1)
        self.ocr_input = SourceEdit()                   # OCR 頁上方：辨識出的原文
        self.ocr_input.setPlaceholderText("截圖後顯示辨識出的原文，可修改後 Enter 重新翻譯")
        self.ocr_translate_btn = QPushButton("翻譯")
        row = QHBoxLayout()
        row.addWidget(QLabel("自動偵測 → 繁體中文"), 1)
        row.addWidget(self.ocr_translate_btn)
        self.ocr_output = QPlainTextEdit()              # OCR 頁下方：譯文
        self.ocr_output.setReadOnly(True)
        self.ocr_output.setFocusPolicy(Qt.ClickFocus)
        col.addLayout(region_row)
        col.addWidget(self.ocr_input, 1)
        col.addLayout(row)
        col.addWidget(self.ocr_output, 1)
        return page

    def _select_tab(self, i):
        self.stack.setCurrentIndex(i)
        for j, b in enumerate(self.tabs):
            b.setChecked(j == i)

    def _select_region(self):
        """從下拉清單選區域：清空九宮格選取。"""
        self.grid_popup.clear()

    def _open_grid(self):
        """在九宮格按鈕右側展開九宮格面板；這次點擊剛把面板收合時不再展開。"""
        if self.grid_popup.closed_by_button:
            self.grid_popup.closed_by_button = False
            return
        self.grid_popup.move(self.grid_btn.mapToGlobal(QPoint(self.grid_btn.width(), 0)))
        self.grid_popup.show()

    def _capture(self):
        self.capture_btn.setEnabled(False)              # 截圖與辨識完成前不重複送出
        # 有選格子時用九宮格，全部未選時用下拉清單的區域（capture.crop_box 以 cells 優先）
        self.capture_requested.emit(self.region_box.currentData(), set(self.grid_popup.cells))

    def hide_now(self):
        """截圖前立即隱藏面板（不播動畫），面板狀態機狀態不變。"""
        self._anim.stop()
        self.hide()

    def show_now(self):
        """截圖後立即顯示面板並取回前景。"""
        self.show()
        self.raise_()
        self.activateWindow()
        platform_win.bring_to_foreground(int(self.winId()))

    def show_ocr_result(self, blocks):
        """辨識完成（UI 執行緒）：文字區塊以換行串成原文，自動翻譯。"""
        self.capture_btn.setEnabled(True)
        self.ocr_input.setPlainText("\n".join(blocks))
        if not self.translate_btn.isEnabled():          # 前一筆翻譯回來後再送出
            self._ocr_pending = True
            return
        self._submit(self.ocr_input, self.ocr_output, True)

    def show_ocr_error(self, reason):
        self.capture_btn.setEnabled(True)
        self._show_status(f"OCR 失敗：{reason}")

    def _show_status(self, text):
        self.status.setText(text)
        self.status.show()
        self._status_timer.start()

    def _show_engine_fields(self):
        current = self.engine_box.currentData()
        for key, w in self.engine_rows.items():
            w.setVisible(key == current)

    def _engine_selected(self):
        self._show_engine_fields()
        self.setting_changed.emit("engine", self.engine_box.currentData())

    def play_expand(self):
        if self.isHidden():
            self._step(1)
            self.show()
        self._slide_to(PANEL_W, EXPAND_MS, EXPAND_CURVE)
        self.raise_()
        self.activateWindow()
        platform_win.bring_to_foreground(int(self.winId()))
        self.setFocus()

    def focus_input(self):
        """把面板帶到前景並讓文字翻譯頁的輸入框取得焦點。"""
        self._select_tab(0)
        self.raise_()
        self.activateWindow()
        platform_win.bring_to_foreground(int(self.winId()))
        self.input.setFocus()

    def _submit(self, edit, output, by_line):
        text = edit.toPlainText().strip()
        if text and self.translate_btn.isEnabled():     # 翻譯中不重複送出（兩頁一次只翻一筆）
            self.translate_btn.setEnabled(False)
            self.ocr_translate_btn.setEnabled(False)
            self._target_output = output
            self.translate_requested.emit(text, by_line)

    def show_result(self, result):
        """翻譯完成（UI 執行緒）：成功顯示譯文，失敗在底部短暫顯示引擎與原因。"""
        self.translate_btn.setEnabled(True)
        self.ocr_translate_btn.setEnabled(True)
        if result.error is None:
            self._target_output.setPlainText(result.text)
        else:
            self._show_status(f"{result.engine} 翻譯失敗：{result.error}")
        if self._ocr_pending:
            self._ocr_pending = False
            self._submit(self.ocr_input, self.ocr_output, True)

    def play_collapse(self):
        self._slide_to(0, COLLAPSE_MS, COLLAPSE_CURVE)

    def _slide_to(self, end, full_ms, curve):
        """從目前寬度滑到 end；動畫中途反向時，時長照剩下的距離比例縮短。"""
        self._anim.stop()
        start = self._width
        # 照 glass.py：設定期間暫停 valueChanged，避免停下的動畫改起點時先送出一個錯位的值
        self._anim.blockSignals(True)
        try:
            self._anim.setEasingCurve(curve)
            self._anim.setDuration(max(1, round(full_ms * abs(end - start) / PANEL_W)))
            self._anim.setStartValue(start)
            self._anim.setEndValue(end)
            self._anim.start()
        finally:
            self._anim.blockSignals(False)

    def _step(self, v):
        self._width = int(v)
        if self._width <= 0:
            self.hide()                                 # 收合播完才隱藏
            return
        g = self.screen_geo
        self.setGeometry(g.x() + g.width() - self._width, g.y() + (g.height() - PANEL_H) // 2,
                         self._width, PANEL_H)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.esc_pressed.emit()
            return
        super().keyPressEvent(e)

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.activated.emit()
        if e.type() == QEvent.ActivationChange and not self.isActiveWindow():
            self.focus_lost.emit()

    def showEvent(self, e):
        super().showEvent(e)
        self._ensure_acrylic()

    def _ensure_acrylic(self):
        if self.use_acrylic and not self._acrylic_tried:
            self._acrylic_tried = True
            try:
                self.acrylic = platform_win.enable_acrylic(int(self.winId()), ACRYLIC_TINT)
            except Exception:                           # 系統 API 失敗就改畫不透明深色底
                self.acrylic = False
            debuglog.log(f"acrylic={self.acrylic} build={platform_win.windows_build()}")  # 暫時 debug：追查偶發的不透明底
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, PANEL_W, PANEL_H).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, PANEL_RADIUS, PANEL_RADIUS)
        if self.use_acrylic:
            if not self.acrylic:
                p.fillRect(self.rect(), PANEL_BG)
        else:
            c = QColor(PANEL_BG)
            c.setAlphaF(0.86)
            p.fillPath(path, c)
        p.setPen(QPen(PANEL_STROKE, 1))
        p.drawPath(path)
