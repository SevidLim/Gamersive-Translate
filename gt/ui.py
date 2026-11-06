"""邊條與面板的 Qt 視窗。開合時機全由面板狀態機決定，這裡只負責畫面與動畫。

面板的毛玻璃做法沿用 Desktop-Agent-Pet 的 src/glass.py：
不設 WA_TranslucentBackground，由 Windows Acrylic 畫模糊；失敗時畫不透明深色底。
側滑也照 glass.py：視窗寬度從 0 變到全寬，內容固定全寬、靠左貼齊，看起來是滑出來。
"""

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gt import debuglog, platform_win

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


class Panel(QWidget):
    """面板：從主螢幕右緣滑出的毛玻璃視窗（本票內容為空殼）。"""

    esc_pressed = Signal()
    focus_lost = Signal()
    animation_done = Signal()

    def __init__(self, screen):
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
        self.setFocusPolicy(Qt.StrongFocus)
        self._width = 0
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._step)
        self._anim.finished.connect(self.animation_done)
        self._ensure_acrylic()                          # 啟動時先套 Acrylic，第一次展開不再等待

    def play_expand(self):
        if self.isHidden():
            self._step(1)
            self.show()
        self._slide_to(PANEL_W, EXPAND_MS, EXPAND_CURVE)
        self.raise_()
        self.activateWindow()
        platform_win.bring_to_foreground(int(self.winId()))
        self.setFocus()

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
