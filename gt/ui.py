"""邊條與面板的 Qt 視窗。開合時機全由面板狀態機決定，這裡只負責畫面與動畫。

面板的毛玻璃做法沿用 Desktop-Agent-Pet 的 src/glass.py：
不設 WA_TranslucentBackground，由 Windows Acrylic 畫模糊；失敗時畫不透明深色底。
側滑也照 glass.py：視窗寬度從 0 變到全寬，內容固定全寬、靠左貼齊，看起來是滑出來。
"""

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QComboBox, QFontComboBox, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

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
FONT_SIZES = (8, 24)                             # 設定頁「大小」範圍（pt），間隔 1
SELECT_DIM = QColor(0, 0, 0, 120)                # 自訂框選：框外變暗
SELECT_STROKE = QColor(255, 255, 255, 220)       # 自訂框選：選取框邊線
HANDLE_HIT = 6                                   # 自訂框選：四角與四邊的拖曳判定範圍（px）
HANDLE_CORNER = 8                                # 自訂框選：四角控制點方形邊長（px）
HANDLE_EDGE = (12, 6)                            # 自訂框選：四邊中點控制點長方形長、寬（px）

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
QSpinBox {{
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
QLabel#status[ok="true"] {{ color: #d7ffdf; background: rgba(20, 110, 50, 0.55); }}
"""


def bezier(x1, y1, x2, y2):
    c = QEasingCurve(QEasingCurve.BezierSpline)
    c.addCubicBezierSegment(QPointF(x1, y1), QPointF(x2, y2), QPointF(1, 1))
    return c


EXPAND_CURVE = bezier(0.16, 1, 0.3, 1)           # 進場
COLLAPSE_CURVE = bezier(0.4, 0, 0.9, 0.35)       # 退場

TOP_FLAGS = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint


def apply_font(family, size):
    """全程式文字改用 family 字型、size pt，字重沿用目前。"""
    f = QApplication.font()
    f.setFamily(family)
    f.setPointSize(size)
    QApplication.setFont(f)
    # 套了 QSS 的元件不會跟著 QApplication.setFont 更新，已建立的元件逐一設定
    for w in QApplication.allWidgets():
        w.setFont(f)


class Strip(QWidget):
    """邊條：貼所選螢幕右緣、垂直置中。"""

    entered = Signal()
    left = Signal()

    def __init__(self, screen):
        super().__init__(None, TOP_FLAGS)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.set_screen(screen)

    def set_screen(self, screen):
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


class RegionSelector(QWidget):
    """自訂框選：在螢幕上以全螢幕置頂視窗顯示凍結畫面，拖出選取框後可拖四角與四邊調整。
    框下方 ✕（取消，Esc）與 ✓（確定，Enter）；accepted 送出螢幕邏輯座標的 (x1, y1, x2, y2)。"""

    accepted = Signal(object)
    cancelled = Signal()

    def __init__(self, screen, frame):
        super().__init__(None, TOP_FLAGS)
        h, w = frame.shape[:2]                          # dxcam 的 BGR 截圖
        self.image = QImage(frame.data, w, h, frame.strides[0], QImage.Format_BGR888).copy()
        self.setGeometry(screen.geometry())
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet(PAGE_QSS)
        self.sel = None                                 # 選取框 [x1, y1, x2, y2]
        self.drag = None                                # 拖曳中："new" 或要移動的邊（l、t、r、b 組合）
        self.origin = QPoint()
        self.cancel_btn = QPushButton("\u2715", self)
        self.ok_btn = QPushButton("\u2713", self)
        f = self.cancel_btn.font()
        f.setPointSizeF(f.pointSizeF() * 0.8)               # ✕ 字形比 ✓ 大，縮小到相近
        self.cancel_btn.setFont(f)
        for b in (self.cancel_btn, self.ok_btn):
            b.setFocusPolicy(Qt.NoFocus)                # 鍵盤焦點留在本視窗，Esc 與 Enter 才有效
            b.hide()
        self.cancel_btn.clicked.connect(self._cancel)
        self.ok_btn.clicked.connect(self._accept)

    def start(self):
        self.show()
        self.raise_()
        self.activateWindow()
        platform_win.bring_to_foreground(int(self.winId()))
        self.setFocus()

    def _edges(self, pos):
        """pos 落在選取框的哪些邊上（l、t、r、b 組合），不在邊上回傳空字串。"""
        if self.sel is None:
            return ""
        x1, y1, x2, y2 = self.sel
        x, y = pos.x(), pos.y()
        if not (x1 - HANDLE_HIT <= x <= x2 + HANDLE_HIT and y1 - HANDLE_HIT <= y <= y2 + HANDLE_HIT):
            return ""
        return "".join(k for k, near in (("l", abs(x - x1) <= HANDLE_HIT), ("t", abs(y - y1) <= HANDLE_HIT),
                                         ("r", abs(x - x2) <= HANDLE_HIT), ("b", abs(y - y2) <= HANDLE_HIT)) if near)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        pos = e.position().toPoint()
        self.drag = self._edges(pos) or "new"
        if self.drag == "new":
            self.origin = pos
            self.sel = [pos.x(), pos.y(), pos.x(), pos.y()]
        self.cancel_btn.hide()
        self.ok_btn.hide()
        self.update()

    def mouseMoveEvent(self, e):
        if self.drag is None:
            return
        x, y = e.position().toPoint().x(), e.position().toPoint().y()
        if self.drag == "new":
            ox, oy = self.origin.x(), self.origin.y()
            self.sel = [min(ox, x), min(oy, y), max(ox, x), max(oy, y)]
        else:
            for k, i, v in (("l", 0, x), ("t", 1, y), ("r", 2, x), ("b", 3, y)):
                if k in self.drag:
                    self.sel[i] = v
        self.update()

    def mouseReleaseEvent(self, e):
        if self.drag is None:
            return
        self.drag = None
        x1, y1, x2, y2 = self.sel                       # 拖過頭時邊對調
        self.sel = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
        self._place_buttons()
        self.update()

    def _place_buttons(self):
        """✕、✓ 放在框下方靠右；下方放不下時放到框上方。"""
        x1, y1, x2, y2 = self.sel
        for b in (self.cancel_btn, self.ok_btn):
            b.adjustSize()
        bw = self.cancel_btn.width() + 8 + self.ok_btn.width()
        y = y2 + 8
        if y + CTL_H > self.height():
            y = max(0, y1 - 8 - CTL_H)
        x = min(max(0, x2 - bw), self.width() - bw)
        self.cancel_btn.move(x, y)
        self.ok_btn.move(x + self.cancel_btn.width() + 8, y)
        self.cancel_btn.show()
        self.ok_btn.show()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._cancel()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._accept()

    def _cancel(self):
        self.close()
        self.cancelled.emit()

    def _accept(self):
        if self.sel is None or self.drag is not None or self.sel[0] == self.sel[2] or self.sel[1] == self.sel[3]:
            return                                      # 還沒有選取框時不送出
        self.close()
        self.accepted.emit(tuple(self.sel))

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawImage(QRectF(self.rect()), self.image)     # 實體像素截圖縮放到邏輯尺寸
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        if self.sel is not None:
            x1, y1, x2, y2 = self.sel
            r = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            hole = QPainterPath()
            hole.addRect(r)
            path = path.subtracted(hole)
        p.fillPath(path, SELECT_DIM)
        if self.sel is not None:
            p.setPen(QPen(SELECT_STROKE, 1))
            p.drawRect(r)
            self._paint_handles(p, r)

    def _paint_handles(self, p, r):
        """四角畫小方形、四邊中點畫小長方形，表示可拖拉（同電腦版微信截圖框）。"""
        p.setPen(Qt.NoPen)
        p.setBrush(SELECT_STROKE)
        c, (long, short) = HANDLE_CORNER, HANDLE_EDGE
        for x, y in ((r.left(), r.top()), (r.right(), r.top()), (r.left(), r.bottom()), (r.right(), r.bottom())):
            p.drawRect(QRectF(x - c / 2, y - c / 2, c, c))
        cx, cy = r.center().x(), r.center().y()
        for x, y in ((cx, r.top()), (cx, r.bottom())):
            p.drawRect(QRectF(x - long / 2, y - short / 2, long, short))
        for x, y in ((r.left(), cy), (r.right(), cy)):
            p.drawRect(QRectF(x - short / 2, y - long / 2, short, long))


class Panel(QWidget):
    """面板：從所選螢幕右緣滑出的毛玻璃視窗，內含文字翻譯、OCR、設定三頁。"""

    esc_pressed = Signal()
    activated = Signal()
    focus_lost = Signal()
    animation_done = Signal()
    translate_requested = Signal(str, bool)      # 原文、是否一行一個文字區塊（OCR 頁）
    capture_requested = Signal(str, object)      # 截圖區域、九宮格格號集合
    setting_changed = Signal(str, object)        # config 欄位名、值
    custom_capture_requested = Signal()          # OCR 頁「自訂框選」
    screen_changed = Signal(object)              # 設定頁選的 QScreen
    animation_changed = Signal(bool)             # 設定頁的動畫開關

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
        title.setStyleSheet("color: #f2f2f5; font-weight: 600; background: transparent;")   # 大小跟全程式
        box.addWidget(title, 0, Qt.AlignTop | Qt.AlignHCenter)
        self.inner.setStyleSheet(PAGE_QSS)
        self.tabs = [QPushButton("文字翻譯"), QPushButton("OCR"), QPushButton("設定")]
        tab_row = QHBoxLayout()
        for i, b in enumerate(self.tabs):
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, i=i: self._select_tab(i))
            if i == 2:
                tab_row.addStretch(1)                   # 設定鈕在同一列最右側
            tab_row.addWidget(b)
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
        self.engine_box = QComboBox()                   # 分頁列下方：翻譯引擎；引擎欄位在設定頁
        for key, engine in ENGINES.items():
            self.engine_box.addItem(engine.name, key)
        self.engine_rows = {}
        settings_page = QWidget()                       # 設定頁：所選引擎的欄位、螢幕、動畫、字型、大小
        settings = QVBoxLayout(settings_page)
        settings.setContentsMargins(0, 0, 0, 0)
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
        self.screen_box = QComboBox()                   # 螢幕：顯示 model 與解析度，記 name
        self.set_screens(QGuiApplication.screens(), screen)
        self.screen_box.activated.connect(lambda _: self.screen_changed.emit(self.screen_box.currentData()))
        self.animation_btn = QPushButton("動畫")
        self.animation_btn.setCheckable(True)
        self.animation_btn.setChecked(cfg["animation"])
        self.animated = cfg["animation"]
        self.animation_btn.toggled.connect(self._animation_toggled)
        screen_row = QHBoxLayout()
        screen_row.addWidget(self.screen_box, 1)
        screen_row.addWidget(self.animation_btn)
        settings.addLayout(screen_row)
        self.font_box = QFontComboBox()                 # 字型：系統字型
        self.font_box.setCurrentFont(QFont(cfg["font_family"]))
        self.font_box.currentFontChanged.connect(self._font_selected)
        self.size_box = QSpinBox()                      # 大小（pt）
        self.size_box.setRange(*FONT_SIZES)
        self.size_box.setValue(cfg["font_size"])
        self.size_box.setSuffix(" pt")
        self.size_box.valueChanged.connect(self._size_selected)
        font_row = QHBoxLayout()
        font_row.addWidget(self.font_box, 1)
        font_row.addWidget(self.size_box)
        settings.addLayout(font_row)
        settings.addStretch(1)
        self.stack.addWidget(settings_page)
        self._select_tab(0)
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
        self.fullscreen_row = QWidget()                 # 偵測到獨佔全螢幕時的提示列
        fs = QHBoxLayout(self.fullscreen_row)
        fs.setContentsMargins(0, 0, 0, 0)
        fs_label = QLabel("偵測到獨佔全螢幕，請將遊戲改為無邊框視窗模式")
        fs_label.setWordWrap(True)
        fs.addWidget(fs_label, 1)
        recheck = QPushButton("重新偵測")
        recheck.clicked.connect(self._recheck_fullscreen)
        fs.addWidget(recheck)
        self.fullscreen_row.hide()
        box.addLayout(tab_row)
        box.addWidget(self.engine_box)
        box.addWidget(self.stack, 1)
        box.addWidget(self.fullscreen_row)
        box.addWidget(self.status)
        self.input.submitted.connect(lambda: self._submit(self.input, self.output, False))
        self.translate_btn.clicked.connect(lambda: self._submit(self.input, self.output, False))
        self.ocr_input.submitted.connect(lambda: self._submit(self.ocr_input, self.ocr_output, True))
        self.ocr_translate_btn.clicked.connect(lambda: self._submit(self.ocr_input, self.ocr_output, True))
        self.capture_btn.clicked.connect(self._capture)
        self.custom_btn.clicked.connect(self._custom_capture)
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
        self.custom_btn = QPushButton("自訂框選")
        region_row.addWidget(self.region_box)
        region_row.addWidget(self.grid_btn)
        region_row.addStretch(1)
        region_row.addWidget(self.custom_btn)
        region_row.addWidget(self.capture_btn)         # 截圖鈕在最右側，自訂框選在它左邊
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

    def set_capture_enabled(self, on):
        """「截圖」與「自訂框選」一起啟用或停用。"""
        self.capture_btn.setEnabled(on)
        self.custom_btn.setEnabled(on)

    def _capture(self):
        self.set_capture_enabled(False)                 # 截圖與辨識完成前不重複送出
        # 有選格子時用九宮格，全部未選時用下拉清單的區域（capture.crop_box 以 cells 優先）
        self.capture_requested.emit(self.region_box.currentData(), set(self.grid_popup.cells))

    def _custom_capture(self):
        self.set_capture_enabled(False)                 # 框選、截圖與辨識完成前不重複送出
        self.custom_capture_requested.emit()

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
        self.set_capture_enabled(True)
        self.ocr_input.setPlainText("\n".join(blocks))
        if not self.translate_btn.isEnabled():          # 前一筆翻譯回來後再送出
            self._ocr_pending = True
            return
        self._submit(self.ocr_input, self.ocr_output, True)

    def show_ocr_error(self, reason):
        self.set_capture_enabled(True)
        self._show_status(f"OCR 失敗：{reason}")

    def _show_status(self, text, ok=False):
        """底部短暫訊息：預設紅底（失敗），ok 為 True 時綠底。"""
        self.status.setProperty("ok", ok)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(text)
        self.status.show()
        self._status_timer.start()

    def _show_engine_fields(self):
        current = self.engine_box.currentData()
        for key, w in self.engine_rows.items():
            w.setVisible(key == current)

    def set_screens(self, screens, current):
        """重建螢幕下拉清單（「{model} {寬}x{高}」），選取 current。"""
        self.screen_box.clear()
        for sc in screens:
            g = sc.geometry()
            self.screen_box.addItem(f"{sc.model()} {g.width()}x{g.height()}", sc)
            if sc is current:
                self.screen_box.setCurrentIndex(self.screen_box.count() - 1)

    def _font_selected(self, font):
        apply_font(font.family(), self.size_box.value())
        self.setting_changed.emit("font_family", font.family())

    def _size_selected(self, size):
        apply_font(self.font_box.currentFont().family(), size)
        self.setting_changed.emit("font_size", size)

    def set_screen(self, screen):
        self.screen_geo = screen.geometry()
        if self._width > 0:
            self._step(self._width)                     # 展開中立即移到新螢幕

    def _animation_toggled(self, on):
        self.animated = on
        self.animation_changed.emit(on)

    def check_fullscreen(self):
        """偵測獨佔全螢幕：偵測到顯示提示列，否則隱藏。"""
        self.fullscreen_row.setVisible(platform_win.exclusive_fullscreen())

    def _recheck_fullscreen(self):
        if platform_win.exclusive_fullscreen():
            self._show_status("依舊不行，請確保已經改為無邊框視窗模式。")
            return
        self._show_status("已確認可正常運作！", ok=True)
        QTimer.singleShot(STATUS_MS, self.fullscreen_row.hide)   # 與綠底訊息同時消失

    def _engine_selected(self):
        self._show_engine_fields()
        self.setting_changed.emit("engine", self.engine_box.currentData())

    def play_expand(self):
        self.check_fullscreen()
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
        """從目前寬度滑到 end；動畫中途反向時，時長照剩下的距離比例縮短。
        動畫關閉時在下一輪事件迴圈直接到終點並送出 animation_done。"""
        self._anim.stop()
        if not self.animated:                       # 放到下一輪事件迴圈，時機與播動畫時一致
            QTimer.singleShot(0, lambda: (self._step(end), self.animation_done.emit()))
            return
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
