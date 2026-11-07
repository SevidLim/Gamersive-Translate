"""邊條與面板的 Qt 視窗。開合時機全由面板狀態機決定，這裡只負責畫面與動畫。

面板的毛玻璃做法沿用 Desktop-Agent-Pet 的 src/glass.py：
不設 WA_TranslucentBackground，由 Windows Acrylic 畫模糊；失敗時畫不透明深色底。
側滑也照 glass.py：視窗寬度從 0 變到全寬，內容固定全寬、靠左貼齊，看起來是滑出來。
"""

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

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


class Panel(QWidget):
    """面板：從主螢幕右緣滑出的毛玻璃視窗，內含文字翻譯頁的輸入框。"""

    esc_pressed = Signal()
    activated = Signal()
    focus_lost = Signal()
    animation_done = Signal()
    translate_requested = Signal(str)            # 原文
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
            for field, hint, secret in engine.fields:
                edit = QLineEdit(cfg[field])
                edit.setPlaceholderText(hint)
                if secret:
                    edit.setEchoMode(QLineEdit.Password)
                edit.editingFinished.connect(lambda f=field, e=edit: self.setting_changed.emit(f, e.text().strip()))
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
        box.addWidget(self.input, 1)
        box.addLayout(row)
        box.addWidget(self.output, 1)
        box.addLayout(settings)
        box.addWidget(self.status)
        self.input.submitted.connect(self._submit)
        self.translate_btn.clicked.connect(self._submit)
        self.setFocusPolicy(Qt.StrongFocus)
        self._width = 0
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._step)
        self._anim.finished.connect(self.animation_done)
        self._ensure_acrylic()                          # 啟動時先套 Acrylic，第一次展開不再等待

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
        """把面板帶到前景並讓輸入框取得焦點。"""
        self.raise_()
        self.activateWindow()
        platform_win.bring_to_foreground(int(self.winId()))
        self.input.setFocus()

    def _submit(self):
        text = self.input.toPlainText().strip()
        if text and self.translate_btn.isEnabled():     # 翻譯中不重複送出
            self.translate_btn.setEnabled(False)
            self.translate_requested.emit(text)

    def show_result(self, result):
        """翻譯完成（UI 執行緒）：成功顯示譯文，失敗在底部短暫顯示引擎與原因。"""
        self.translate_btn.setEnabled(True)
        if result.error is None:
            self.output.setPlainText(result.text)
            return
        self.status.setText(f"{result.engine} 翻譯失敗：{result.error}")
        self.status.show()
        self._status_timer.start()

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
