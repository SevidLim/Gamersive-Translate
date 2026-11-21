"""邊條與面板的 Qt 視窗。開合時機全由面板狀態機決定，這裡只負責畫面與動畫。

面板的毛玻璃做法沿用 Desktop-Agent-Pet 的 src/glass.py：
不設 WA_TranslucentBackground，由 Windows Acrylic 畫模糊；失敗時畫不透明深色底。
側滑也照 glass.py：視窗寬度從 0 變到全寬，內容固定全寬、靠左貼齊，看起來是滑出來。
"""

from PySide6.QtCore import (QEasingCurve, QEvent, QPoint, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, QUrl,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QImage, QPainter, QPainterPath, QPen,
                           QTextCursor)
from PySide6.QtWidgets import (QApplication, QComboBox, QFontComboBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QSpinBox, QStackedWidget,
                               QSystemTrayIcon, QTextEdit, QVBoxLayout, QWidget)

from gt import platform_win
from gt.search import google_search_url
from gt.translate import ENGINES, LANG_NAMES

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
EXPAND_MS = 250                                  # 面板展開
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
LISTEN_MARGIN = 6                                # 圖示鈕與文字框右下角的距離、圖示鈕之間的距離（px）
ROMAN_MAX_H = 96                                 # 拼音區高度上限（px），超出時捲動
ROMAN_PAD = 6                                    # 拼音區虛線與拼音、拼音與框底的距離（px）
COPIED_MS = 3000                                 # 「已複製」氣泡顯示多久
DONE_MS = 800                                    # loading 完成後 ✓ 顯示多久
SHAKE_MS = 300                                   # 聆聽鈕換回 🔊 後的左右晃動
SHAKE_KEYS = ((0.25, 25), (0.5, -16), (0.75, 8), (1.0, 0))  # 以圖示中心左右晃動的角度（度）
STOP_ICON = "\u23F9"                             # 聆聽鈕播放中的停止圖示 ⏹
DONE_BG = QColor(0xA5, 0xCF, 0x83)              # 聆聽鈕 ✓ 的綠底 #A5CF83
DONE_BG_ALPHA = 0.8                              # 亮綠底的不透明度
SPIN_MS = 1000                                   # loading 圈轉一圈
SPIN_SPAN = 270                                  # loading 圈弧線長度（度）
SPIN_PEN = 2                                     # loading 圈線寬（px）
SPIN_INSET = 8                                   # loading 圈與圓形邊緣的距離（px）
BTN_BG = QColor(255, 255, 255, 36)               # 同 QSS QPushButton 底色 0.14
BTN_STROKE = QColor(255, 255, 255, 51)           # 同 QSS QPushButton 邊框 0.20
BTN_TEXT = QColor(242, 242, 245)                 # 同 QSS 文字色 #f2f2f5
SWITCH_W, SWITCH_H = 44, 24                      # 面板位置開關的軌道寬、高（px）
SWITCH_KNOB_PAD = 3                              # 開關圓鈕與軌道邊緣的距離（px）
SWITCH_MS = 180                                  # 開關圓鈕滑動（位移 160–200ms）
SIDE_NAMES = {"left": "左側", "right": "右側"}
CONFIRM_BG = "rgba(32, 32, 40, 0.93)"            # 確認浮層：固定深灰 0.93
WIDGET_MAX_H = 16777215                          # Qt 元件高度上限的預設值（QWIDGETSIZE_MAX），即不限高度

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
QPushButton#icon {{ padding: 0; min-width: {CTL_H - 2}px; max-width: {CTL_H - 2}px; }}  /* 圓形圖示鈕 */
QFrame#sourceBox {{  /* 原文框：外觀同 QPlainTextEdit，框內是原文輸入與拼音 */
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.16); border-radius: {FIELD_RADIUS}px;
}}
QFrame#sourceBox[focused="true"] {{ border-color: rgba(255, 255, 255, 0.40); }}
QFrame#sourceBox QPlainTextEdit {{ background: transparent; border: none; }}
QTextEdit#roman {{  /* 上緣的灰色虛線隔開原文與拼音 */
    color: rgba(242, 242, 245, 0.55); background: transparent;
    border: none; border-top: 1px dashed rgba(242, 242, 245, 0.35);
    margin: 0 {FIELD_PAD_X}px; padding: {ROMAN_PAD}px 0;
}}
QLabel#bubble {{ background: rgba(32, 32, 40, 0.80); border-radius: {FIELD_RADIUS}px; padding: 6px 10px; }}  /* 深色浮層，同 POPUP_BG */
"""


# 系統匣右鍵選單：深色浮層、圓角（視覺規格）
TRAY_MENU_QSS = f"""
QMenu {{
    color: #f2f2f5; background: rgba(32, 32, 40, 0.80);
    border: 1px solid rgba(255, 255, 255, 0.16); border-radius: {FIELD_RADIUS}px; padding: 4px;
}}
QMenu::item {{ padding: 6px 16px; border-radius: {FIELD_RADIUS - 4}px; }}
QMenu::item:selected {{ background: rgba(255, 255, 255, 0.14); }}
"""


def make_tray(icon_path, on_quit):
    """系統匣圖示：圖示為 icon_path，右鍵選單只有「結束」（呼叫 on_quit）。"""
    menu = QMenu()
    menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WA_TranslucentBackground)       # 圓角外的區域透明
    menu.setStyleSheet(TRAY_MENU_QSS)
    menu.addAction("結束", on_quit)
    tray = QSystemTrayIcon(QIcon(str(icon_path)))
    tray.setToolTip("Gamersive-Translate")
    tray.setContextMenu(menu)
    tray.menu = menu                                    # QSystemTrayIcon 不持有選單，保留參照
    return tray


def bezier(x1, y1, x2, y2):
    c = QEasingCurve(QEasingCurve.BezierSpline)
    c.addCubicBezierSegment(QPointF(x1, y1), QPointF(x2, y2), QPointF(1, 1))
    return c


EXPAND_CURVE = bezier(0.16, 1, 0.3, 1)           # 進場
MOVE_CURVE = bezier(0.2, 0.9, 0.3, 1)            # 位移
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


def edge_x(geo, side, width):
    """寬 width 的視窗貼螢幕 geo 的 side 緣（"left"／"right"）時的 x。"""
    return geo.x() if side == "left" else geo.x() + geo.width() - width


class Strip(QWidget):
    """邊條：貼所選螢幕左緣或右緣（side）、垂直置中。"""

    entered = Signal()
    left = Signal()

    def __init__(self, screen, side):
        super().__init__(None, TOP_FLAGS)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.side = side
        self.set_screen(screen)

    def set_screen(self, screen):
        self._screen = screen
        g = screen.geometry()
        self.setGeometry(edge_x(g, self.side, STRIP_W), g.y() + (g.height() - STRIP_H) // 2, STRIP_W, STRIP_H)

    def set_side(self, side):
        self.side = side
        self.set_screen(self._screen)

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


def target_box(cfg, key, changed):
    """目標語言下拉選單：選項取自 LANG_NAMES，初始值為 cfg[key]；選了呼叫 changed(key, 語言代碼)。"""
    box = QComboBox()
    for code, name in LANG_NAMES.items():
        box.addItem(name, code)
    box.setCurrentIndex(max(0, box.findData(cfg[key])))
    box.currentIndexChanged.connect(lambda _: changed(key, box.currentData()))
    return box


class SourceEdit(QPlainTextEdit):
    """原文輸入框：Enter 送出，Shift+Enter 換行；第一行按上移到開頭，最後一行按下移到結尾。"""

    submitted = Signal()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not e.modifiers() & Qt.ShiftModifier:
            self.submitted.emit()
            return
        if e.key() in (Qt.Key_Up, Qt.Key_Down) and not e.modifiers():
            cursor = self.textCursor()
            up = e.key() == Qt.Key_Up
            probe = QTextCursor(cursor)
            if not probe.movePosition(QTextCursor.Up if up else QTextCursor.Down):   # 已在第一行／最後一行
                cursor.movePosition(QTextCursor.Start if up else QTextCursor.End)
                self.setTextCursor(cursor)
                return
        super().keyPressEvent(e)


class SideSwitch(QWidget):
    """面板位置的滑動開關：圓鈕在左＝左側、在右＝右側。點一下圓鈕滑到另一側並送出 requested(另一側)；
    set_side() 以 SWITCH_MS 滑到指定側（animated 為 False 時直接移過去）。"""

    requested = Signal(str)

    def __init__(self, side):
        super().__init__()
        self.setFixedSize(SWITCH_W, SWITCH_H)
        self.setCursor(Qt.PointingHandCursor)
        self.animated = True
        self.side = side
        self._pos = 0.0 if side == "left" else 1.0     # 0＝左，1＝右
        self._anim = QVariantAnimation(self)
        self._anim.setEasingCurve(MOVE_CURVE)
        self._anim.setDuration(SWITCH_MS)
        self._anim.valueChanged.connect(self._set_pos)

    def set_side(self, side):
        self.side = side
        end = 0.0 if side == "left" else 1.0
        self._anim.stop()
        if not self.animated:
            self._set_pos(end)
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(end)
        self._anim.start()

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            target = "right" if self.side == "left" else "left"
            self.set_side(target)
            self.requested.emit(target)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(BTN_STROKE, 1))
        p.setBrush(BTN_BG)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 2 * SWITCH_KNOB_PAD
        x = r.left() + SWITCH_KNOB_PAD + (r.width() - 2 * SWITCH_KNOB_PAD - d) * self._pos
        p.setPen(Qt.NoPen)
        p.setBrush(BTN_TEXT)
        p.drawEllipse(QRectF(x, r.top() + SWITCH_KNOB_PAD, d, d))


class ConfirmOverlay(QFrame):
    """面板正中央的深色確認浮層：ask(文字) 顯示，「確定」送出 accepted、「取消」送出 rejected；
    淡入 EXPAND_MS、淡出 COLLAPSE_MS，淡出播完才隱藏；animated 為 False 時直接顯示與隱藏。"""

    accepted = Signal()
    rejected = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("confirm")
        self.setStyleSheet(f"QFrame#confirm {{ background: {CONFIRM_BG}; border-radius: {PANEL_RADIUS}px; }}")
        self.animated = True
        col = QVBoxLayout(self)
        col.setContentsMargins(20, 16, 20, 16)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        col.addWidget(self.label)
        row = QHBoxLayout()
        self.ok_btn = QPushButton("確定")
        self.cancel_btn = QPushButton("取消")
        for b in (self.ok_btn, self.cancel_btn):
            b.setAutoDefault(True)                      # 焦點所在的按鈕按 Enter 觸發
        row.addWidget(self.ok_btn)
        row.addWidget(self.cancel_btn)
        col.addLayout(row)
        self.ok_btn.clicked.connect(lambda: self._close(self.accepted))
        self.cancel_btn.clicked.connect(lambda: self._close(self.rejected))
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.finished.connect(self._fade_done)
        self._closing = False
        self.hide()

    def ask(self, text):
        self.label.setText(text)
        self.adjustSize()
        p = self.parentWidget()
        self.move((p.width() - self.width()) // 2, (p.height() - self.height()) // 2)
        self._closing = False
        self.show()
        self.raise_()
        self.ok_btn.setFocus()                          # Enter＝確定
        self._fade(1.0, EXPAND_MS, EXPAND_CURVE)

    def is_open(self):
        return self.isVisible() and not self._closing

    def keyPressEvent(self, e):
        """Enter＝確定，Esc＝取消；按鍵不再往面板傳。"""
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._close(self.accepted)
        elif e.key() == Qt.Key_Escape:
            self._close(self.rejected)
        else:
            super().keyPressEvent(e)

    def cancel(self):
        """面板收合等情況：顯示中時當作按了「取消」。"""
        if self.isVisible() and not self._closing:
            self._close(self.rejected)

    def _close(self, signal):
        self._closing = True
        self._fade(0.0, COLLAPSE_MS, COLLAPSE_CURVE)
        signal.emit()

    def _fade(self, end, ms, curve):
        self._anim.stop()
        if not self.animated:
            self._effect.setOpacity(end)
            self._fade_done()
            return
        self._anim.setEasingCurve(curve)
        self._anim.setDuration(ms)
        self._anim.setStartValue(self._effect.opacity() if self.isVisible() and end == 0.0 else 0.0)
        self._anim.setEndValue(end)
        self._anim.start()

    def _fade_done(self):
        if self._closing:
            self.hide()


class LoadingButton(QPushButton):
    """可進入 loading 的按鈕：start_loading() 換成旋轉的 loading 圈，finish(ok) 結束；
    成功時顯示 ✓ DONE_MS 再換回原本內容，失敗時直接換回。loading 與 ✓ 期間停用。
    morph 為 True 時膠囊先收縮成圓形（COLLAPSE_MS）再旋轉，結束時展開回膠囊（EXPAND_MS）；
    按鈕外框大小固定，變形畫在框內。animated 為 False 時直接切換，loading 圈靜止。
    celebrate 為 True 時（聆聽鈕）：✓ 為綠底，✓ 顯示完直接換成 ⏹（playing）；✓ 與 ⏹ 期間可按。
    ended()（播放結束或按下停止）時，目前的 ✓ 或 ⏹ 縮小（COLLAPSE_MS，✓ 的綠底同步淡出），
    原圖示由 0 放大（EXPAND_MS）後左右晃動（SHAKE_MS）；animated 為 False 時直接換回。"""

    def __init__(self, text, morph=False, celebrate=False):
        super().__init__(text)
        self.morph = morph
        self.celebrate = celebrate
        self.animated = True
        self.state = "idle"                             # idle、loading、closing、done、playing、returning
        self._want_enabled = True                       # 外部要求的啟用狀態
        self._shape = 0.0                               # 0＝膠囊，1＝圓形
        self._angle = 0.0
        self._ok = False
        self._phase = None                              # 換回動畫：shrink、grow、shake
        self._from = None                               # 縮小的圖示：check（✓）或 stop（⏹）
        self._ret = 0.0                                 # shrink、grow 的比例；shake 的角度
        self._shape_anim = QVariantAnimation(self)
        self._shape_anim.valueChanged.connect(self._set_shape)
        self._shape_anim.finished.connect(self._shape_done)
        self._spin = QVariantAnimation(self)
        self._spin.setStartValue(0.0)
        self._spin.setEndValue(360.0)
        self._spin.setDuration(SPIN_MS)
        self._spin.setLoopCount(-1)
        self._spin.valueChanged.connect(self._set_angle)
        self._ret_anim = QVariantAnimation(self)
        self._ret_anim.valueChanged.connect(self._set_ret)
        self._ret_anim.finished.connect(self._ret_done)
        self._done_timer = QTimer(self)
        self._done_timer.setSingleShot(True)
        self._done_timer.setInterval(DONE_MS)
        self._done_timer.timeout.connect(self._after_done)

    def _pressable(self):
        return self.state == "idle" or (self.celebrate and self.state in ("done", "playing"))

    def _apply_enabled(self):
        super().setEnabled(self._want_enabled and self._pressable())

    def setEnabled(self, on):
        self._want_enabled = on
        self._apply_enabled()

    def start_loading(self):
        self._done_timer.stop()
        self._stop_return()
        self.state = "loading"
        self._apply_enabled()
        self._angle = 0.0
        if self.morph and self.animated:
            self._animate_shape(1.0, COLLAPSE_MS, COLLAPSE_CURVE)
        else:
            self._shape_anim.stop()
            self._shape = 1.0 if self.morph else 0.0
            self._shape_done()
        self.update()

    def finish(self, ok):
        """結束 loading；不在 loading 時不動作。"""
        if self.state != "loading":
            return
        self._spin.stop()
        self._ok = ok
        self.state = "closing"
        if self.morph and self.animated:
            self._animate_shape(0.0, EXPAND_MS, EXPAND_CURVE)
        else:
            self._shape_anim.stop()
            self._shape = 0.0
            self._shape_done()
        self.update()

    def ended(self):
        """播放結束或按下停止：✓ 或 ⏹ 換回原圖示；其他狀態不動作。"""
        if self.state == "done" and self.celebrate:
            self._done_timer.stop()
            self._begin_return("check")
        elif self.state == "playing":
            self._begin_return("stop")

    def _animate_shape(self, end, ms, curve):
        self._shape_anim.stop()
        self._shape_anim.setEasingCurve(curve)
        self._shape_anim.setDuration(ms)
        self._shape_anim.setStartValue(self._shape)
        self._shape_anim.setEndValue(end)
        self._shape_anim.start()

    def _set_shape(self, v):
        self._shape = float(v)
        self.update()

    def _set_angle(self, v):
        self._angle = float(v)
        self.update()

    def _shape_done(self):
        if self.state == "loading":                     # 收縮完成：開始旋轉
            if self.animated:
                self._spin.start()
        elif self.state == "closing":                   # 展開完成：成功顯示 ✓，失敗換回
            if self._ok:
                self.state = "done"
                self._apply_enabled()
                self._done_timer.start()
            else:
                self._to_idle()
        self.update()

    def _after_done(self):
        """✓ 顯示完：聆聽鈕換成 ⏹，其他按鈕換回。"""
        if self.celebrate:
            self.state = "playing"
            self._apply_enabled()
            self.update()
        else:
            self._to_idle()

    def _to_idle(self):
        self.state = "idle"
        self._apply_enabled()
        self.update()

    def _begin_return(self, glyph):
        if not self.animated:
            self._to_idle()
            return
        self.state = "returning"
        self._from = glyph
        self._apply_enabled()
        self._run_phase("shrink")

    def _run_phase(self, phase):
        a = self._ret_anim
        a.stop()
        self._phase = phase
        a.blockSignals(True)                            # 設定期間清空關鍵影格會送出值為 None 的 valueChanged
        try:
            a.setKeyValues([])                          # 清掉上一段（晃動）的關鍵影格
            if phase == "shake":
                a.setEasingCurve(QEasingCurve.Linear)
                a.setDuration(SHAKE_MS)
                a.setStartValue(0.0)
                for t, deg in SHAKE_KEYS:
                    a.setKeyValueAt(t, float(deg))
            else:
                shrink = phase == "shrink"
                a.setEasingCurve(COLLAPSE_CURVE if shrink else EXPAND_CURVE)
                a.setDuration(COLLAPSE_MS if shrink else EXPAND_MS)
                a.setStartValue(1.0 if shrink else 0.0)
                a.setEndValue(0.0 if shrink else 1.0)
            self._ret = float(a.startValue())
            a.start()
        finally:
            a.blockSignals(False)
        self.update()

    def _set_ret(self, v):
        self._ret = float(v)
        self.update()

    def _ret_done(self):
        if self._phase == "shrink":
            QPushButton.setEnabled(self, self._want_enabled)     # 🔊 開始放大起即可再按
            self._run_phase("grow")
        elif self._phase == "grow":
            self._run_phase("shake")
        elif self._phase == "shake":
            self._phase = None
            self._to_idle()

    def _stop_return(self):
        self._ret_anim.stop()
        self._phase = None

    def paintEvent(self, e):
        if self.state == "idle":
            super().paintEvent(e)
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        h = r.height()
        if self.state in ("returning", "playing"):
            self._paint_bg(p, r)
            if self.state == "playing":
                self._paint_scaled(p, r, 1.0, 0.0, STOP_ICON)
            else:
                self._paint_return(p, r)
            return
        w = r.width() - (r.width() - h) * self._shape    # 膠囊寬度往圓形（寬＝高）縮
        self._paint_bg(p, QRectF(r.center().x() - w / 2, r.top(), w, h))
        if self.state == "loading" and (self._shape >= 1.0 or not self.morph):
            d = h - 2 * SPIN_INSET
            arc = QRectF(r.center().x() - d / 2, r.center().y() - d / 2, d, d)
            p.setPen(QPen(BTN_TEXT, SPIN_PEN, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawArc(arc, int(-self._angle * 16), SPIN_SPAN * 16)
        elif self.state == "done":
            if self.celebrate:
                self._paint_check(p, r, 1.0)
            else:
                p.setPen(BTN_TEXT)
                p.drawText(self.rect(), Qt.AlignCenter, "\u2713")

    def _paint_bg(self, p, shape):
        p.setPen(QPen(BTN_STROKE, 1))
        p.setBrush(BTN_BG)
        p.drawRoundedRect(shape, shape.height() / 2, shape.height() / 2)

    def _paint_check(self, p, r, s):
        """綠底 ✓，大小與綠底不透明度乘上比例 s。"""
        bg = QColor(DONE_BG)
        bg.setAlphaF(DONE_BG_ALPHA * s)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        self._paint_scaled(p, r, s, 0.0, "\u2713")

    def _paint_scaled(self, p, r, s, deg, text):
        """以 r 中心縮放 s、旋轉 deg 度畫 text。"""
        if s <= 0:
            return
        p.save()
        c = r.center()
        p.translate(c)
        p.rotate(deg)
        p.scale(s, s)
        p.translate(-c)
        p.setPen(BTN_TEXT)
        p.drawText(self.rect(), Qt.AlignCenter, text)
        p.restore()

    def _paint_return(self, p, r):
        """換回動畫：✓ 或 ⏹ 縮小（✓ 的綠底同步淡出），原圖示放大，左右晃動。"""
        if self._phase == "shrink":
            if self._from == "check":
                self._paint_check(p, r, self._ret)
            else:
                self._paint_scaled(p, r, self._ret, 0.0, STOP_ICON)
        elif self._phase == "grow":
            self._paint_scaled(p, r, self._ret, 0.0, self.text())
        else:
            self._paint_scaled(p, r, 1.0, self._ret, self.text())


class TextButtons(QWidget):
    """文字框右下角由左到右的聆聽、複製、Google 搜索三個圖示鈕，原文框與譯文框共用；
    疊在框 box 上，跟著框與框內文字輸入 edit 的大小移動；edit 為空時隱藏。
    聆聽：送出 listen_requested(edit 的文字)。複製：edit 的文字放進剪貼簿，複製鈕上方顯示「已複製」氣泡 COPIED_MS。
    Google 搜索：以預設瀏覽器搜尋 edit 的文字。"""

    listen_requested = Signal(str)               # 要聆聽的文字

    def __init__(self, box, edit):
        super().__init__(box)
        self.box = box
        self.edit = edit
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(LISTEN_MARGIN)
        self.listen_btn = LoadingButton("\U0001F50A", celebrate=True)    # 聆聽：按下後 loading，開始播放時 ✓
        self.copy_btn, self.search_btn = (QPushButton(icon) for icon in ("\u29C9", "\U0001F50D"))
        for b, tip in ((self.listen_btn, "聆聽"), (self.copy_btn, "複製"), (self.search_btn, "Google 搜索")):
            b.setObjectName("icon")
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.NoFocus)                # 不搶走輸入焦點
            b.setFixedSize(CTL_H, CTL_H)
            row.addWidget(b)
        self.adjustSize()
        self.bubble = QLabel("已複製", box)             # 疊在框上層的子元件，不成為獨立視窗
        self.bubble.setObjectName("bubble")
        self.bubble.hide()
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.setInterval(COPIED_MS)
        self._bubble_timer.timeout.connect(self.bubble.hide)
        self.listen_btn.clicked.connect(lambda: self.listen_requested.emit(edit.toPlainText()))
        self.copy_btn.clicked.connect(self._copy)
        self.search_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(google_search_url(edit.toPlainText()))))
        box.installEventFilter(self)
        edit.viewport().installEventFilter(self)
        edit.textChanged.connect(self._sync)
        self._sync()

    def eventFilter(self, obj, e):
        if e.type() == QEvent.Resize:                   # 框或文字區大小改變（含捲軸出現）：貼回右下角
            g = self.edit.viewport().geometry()         # 與框邊的距離同文字區與 edit 邊緣的距離
            o = self.edit.mapTo(self.box, QPoint(0, 0))
            self.move(o.x() + g.x() + g.width() - self.width() - LISTEN_MARGIN,
                      self.box.height() - o.y() - g.y() - self.height() - LISTEN_MARGIN)
        return False

    def _sync(self):
        self.setVisible(bool(self.edit.toPlainText().strip()))

    def _copy(self):
        QGuiApplication.clipboard().setText(self.edit.toPlainText())
        self.bubble.adjustSize()
        pos = self.copy_btn.mapTo(self.box, QPoint(0, 0))       # 氣泡置中在複製鈕上方
        self.bubble.move(pos.x() + (self.copy_btn.width() - self.bubble.width()) // 2,
                         pos.y() - self.bubble.height() - LISTEN_MARGIN)
        self.bubble.show()
        self.bubble.raise_()
        self._bubble_timer.start()


class RomanView(QTextEdit):
    """拼音區：唯讀、自動換行、灰色文字，上緣一條灰色虛線；高度隨內容，最高 ROMAN_MAX_H，超出時捲動；
    沒有拼音時連同虛線隱藏。"""

    def __init__(self):
        super().__init__()
        self.setObjectName("roman")
        self.setReadOnly(True)
        self.document().documentLayout().documentSizeChanged.connect(self._fit)
        self.hide()

    def _fit(self, size):
        self.setFixedHeight(min(int(size.height()) + 2 * ROMAN_PAD + 1, ROMAN_MAX_H))   # QSS：上下內距與 1px 虛線

    def set_roman(self, text):
        self.setPlainText(text)
        self.setVisible(bool(text))


class SourceBox(QFrame):
    """原文框：同一個框（邊框、底色、圓角）內由上到下是原文輸入 edit、拼音區 roman（上緣為虛線），
    右下角疊聆聽、複製、Google 搜索三個圖示鈕 btns；edit 取得焦點時框的邊框變亮。
    有拼音時 edit 的高度隨原文內容，虛線與拼音緊接在原文下方，其下留白，原文超出時 edit 捲動；
    沒有拼音時 edit 佔滿整個框。點框內留白處時焦點進 edit。"""

    def __init__(self, placeholder):
        super().__init__()
        self.setObjectName("sourceBox")
        self.edit = SourceEdit()
        self.edit.setPlaceholderText(placeholder)
        self.roman = RomanView()
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self.edit, 1)
        col.addWidget(self.roman)
        col.addStretch()                                # 有拼音時拼音下方的留白
        self.btns = TextButtons(self, self.edit)
        self.edit.installEventFilter(self)
        self.roman.installEventFilter(self)
        self.edit.document().documentLayout().documentSizeChanged.connect(self._fit)

    def eventFilter(self, obj, e):
        if obj is self.edit and e.type() in (QEvent.FocusIn, QEvent.FocusOut):
            self.setProperty("focused", e.type() == QEvent.FocusIn)
            self.style().unpolish(self)
            self.style().polish(self)
        if obj is self.roman and e.type() in (QEvent.ShowToParent, QEvent.HideToParent):
            self._fit()
        return False

    def mousePressEvent(self, e):
        self.edit.setFocus()

    def _fit(self):
        """有拼音時 edit 最高到原文內容的高度，沒有拼音時不限高度。"""
        if self.roman.isHidden():
            self.edit.setMaximumHeight(WIDGET_MAX_H)
            return
        doc, m = self.edit.document(), self.edit.contentsMargins()      # m：QSS 內距
        h, block = 2 * doc.documentMargin() + m.top() + m.bottom(), doc.begin()
        while block.isValid():
            h += doc.documentLayout().blockBoundingRect(block).height()
            block = block.next()
        self.edit.setMaximumHeight(int(h))


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
    listen_requested = Signal(str)               # 要聆聽的文字
    listen_stop_requested = Signal()             # 停止聆聽（清除鈕、⏹）
    side_changed = Signal(str)                   # 設定頁確認後的面板位置："left"／"right"

    def __init__(self, screen, cfg):
        super().__init__(None, TOP_FLAGS)
        self.screen_geo = screen.geometry()
        self.side = cfg["side"]                         # 面板位置："left"／"right"
        self.use_acrylic = platform_win.IS_WIN
        if not self.use_acrylic:
            self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("glassPanel")             # 照 glass.py：視窗底透明，模糊由系統畫
        self.setStyleSheet("QWidget#glassPanel { background: transparent; }")
        self.acrylic = False
        self._acrylic_tried = False
        self.inner = QWidget(self)                      # 固定全寬，貼面板位置的反側，視窗變寬時露出來
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
        self.target_box = target_box(cfg, "target_lang", self.setting_changed.emit)     # 文字翻譯頁的目標語言
        langs = self._lang_row(self.target_box)
        self.input_box = SourceBox("輸入原文，Enter 翻譯，Shift+Enter 換行")    # 文字翻譯頁上方：原文框
        self.input = self.input_box.edit                # 原文
        self.listen_btn = self.input_box.btns.listen_btn    # 原文框右下角：聆聽、複製、Google 搜索
        self.input_box.btns.listen_requested.connect(lambda text: self._listen(0, text, self.listen_btn))
        self.roman = self.input_box.roman               # 原文框內、原文下方：該次送出原文的拼音
        self.clear_btn = QPushButton("清除")             # 「翻譯」鈕左邊：清空這一頁
        self.translate_btn = LoadingButton("翻譯", morph=True)
        row = QHBoxLayout()
        row.addLayout(langs, 1)
        row.addWidget(self.clear_btn)
        row.addWidget(self.translate_btn)
        self.output = QPlainTextEdit()                  # 文字翻譯頁下方：譯文
        self.output.setReadOnly(True)
        self.output.setFocusPolicy(Qt.ClickFocus)
        self.output_btns = TextButtons(self.output, self.output)    # 譯文框右下角：聆聽、複製、Google 搜索
        self.output_btns.listen_requested.connect(lambda text: self._listen(0, text, self.output_btns.listen_btn))
        text_box.addWidget(self.input_box, 1)
        text_box.addLayout(row)
        text_box.addWidget(self.output, 1)
        self.stack.addWidget(text_page)
        self.ocr_target_box = target_box(cfg, "ocr_target_lang", self.setting_changed.emit)   # OCR 頁的目標語言
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
        self.loading_btns = [self.translate_btn, self.ocr_translate_btn, self.capture_btn, self.listen_btn,
                             self.output_btns.listen_btn, self.ocr_listen_btn, self.ocr_output_btns.listen_btn]
        for b in self.loading_btns:
            b.animated = self.animated
        self.animation_btn.toggled.connect(self._animation_toggled)
        screen_row = QHBoxLayout()
        screen_row.addWidget(self.screen_box, 1)
        screen_row.addWidget(self.animation_btn)
        settings.addLayout(screen_row)
        self.side_switch = SideSwitch(self.side)        # 面板位置：圓鈕在左＝左側、在右＝右側
        self.side_switch.animated = self.animated
        self.side_switch.requested.connect(self._side_requested)
        side_row = QHBoxLayout()
        side_row.addWidget(QLabel("面板位置"))
        side_row.addStretch(1)
        side_row.addWidget(QLabel(SIDE_NAMES["left"]))
        side_row.addWidget(self.side_switch)
        side_row.addWidget(QLabel(SIDE_NAMES["right"]))
        settings.addLayout(side_row)
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
        self.clear_btn.clicked.connect(self._clear_text)
        self.ocr_clear_btn.clicked.connect(self._clear_ocr)
        self.ocr_input.submitted.connect(lambda: self._submit(self.ocr_input, self.ocr_output, True))
        self.ocr_translate_btn.clicked.connect(lambda: self._submit(self.ocr_input, self.ocr_output, True))
        self.capture_btn.clicked.connect(self._capture)
        self.custom_btn.clicked.connect(self._custom_capture)
        self._target_output = self.output                # 翻譯結果要顯示的譯文框
        self._ocr_pending = False                       # 辨識完成時有翻譯進行中，OCR 翻譯待送出
        self._translating = None                        # 翻譯進行中時為送出那一頁的翻譯鈕
        self._listen_page = None                        # 最近一次聆聽來自哪一頁（分頁編號）
        self._listen_btn = None                         # 最近一次按下的聆聽鈕
        self.setFocusPolicy(Qt.StrongFocus)
        self._width = 0
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._step)
        self._anim.finished.connect(self.animation_done)
        self.confirm = ConfirmOverlay(self.inner)       # 面板正中央的確認浮層，最後建立才疊在最上層
        self.confirm.animated = self.animated
        self._lockable = [*self.tabs, self.engine_box, self.stack]  # 確認浮層顯示期間停用
        self.confirm.accepted.connect(lambda: (self._set_locked(False), self.side_changed.emit(self.side_switch.side)))
        self.confirm.rejected.connect(lambda: (self._set_locked(False), self.side_switch.set_side(self.side)))
        self._ensure_acrylic()                          # 啟動時先套 Acrylic，第一次展開不再等待

    def _lang_row(self, box):
        """語言標示「自動偵測 →」加目標語言選單。"""
        row = QHBoxLayout()
        row.addWidget(QLabel("自動偵測 →"))
        row.addWidget(box)
        row.addStretch(1)
        return row

    def _build_ocr_page(self):
        """OCR 頁：截圖區域選擇列、截圖按鈕；上方原文（可修改後重新翻譯）與拼音，下方譯文。"""
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
        self.capture_btn = LoadingButton("截圖", morph=True)
        self.custom_btn = QPushButton("自訂框選")
        region_row.addWidget(self.region_box)
        region_row.addWidget(self.grid_btn)
        region_row.addStretch(1)
        region_row.addWidget(self.custom_btn)
        region_row.addWidget(self.capture_btn)         # 截圖鈕在最右側，自訂框選在它左邊
        self.ocr_input_box = SourceBox("截圖後顯示辨識出的原文，可修改後 Enter 重新翻譯")   # OCR 頁上方：原文框
        self.ocr_input = self.ocr_input_box.edit        # 辨識出的原文
        self.ocr_listen_btn = self.ocr_input_box.btns.listen_btn    # 原文框右下角：聆聽、複製、Google 搜索
        self.ocr_input_box.btns.listen_requested.connect(lambda text: self._listen(1, text, self.ocr_listen_btn))
        self.ocr_roman = self.ocr_input_box.roman       # 原文框內、原文下方：該次送出原文的拼音
        self.ocr_clear_btn = QPushButton("清除")         # 「翻譯」鈕左邊：清空這一頁
        self.ocr_translate_btn = LoadingButton("翻譯", morph=True)
        row = QHBoxLayout()
        row.addLayout(self._lang_row(self.ocr_target_box), 1)
        row.addWidget(self.ocr_clear_btn)
        row.addWidget(self.ocr_translate_btn)
        self.ocr_output = QPlainTextEdit()              # OCR 頁下方：譯文
        self.ocr_output.setReadOnly(True)
        self.ocr_output.setFocusPolicy(Qt.ClickFocus)
        self.ocr_output_btns = TextButtons(self.ocr_output, self.ocr_output)    # 譯文框右下角：聆聽、複製、Google 搜索
        self.ocr_output_btns.listen_requested.connect(
            lambda text: self._listen(1, text, self.ocr_output_btns.listen_btn))
        col.addLayout(region_row)
        col.addWidget(self.ocr_input_box, 1)
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
        self.capture_btn.start_loading()
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

    def capture_loading(self):
        """自訂框選按 ✓ 後：截圖鈕進入 loading。"""
        self.capture_btn.start_loading()

    def show_ocr_result(self, blocks):
        """辨識完成（UI 執行緒）：截圖鈕顯示 ✓，文字區塊以換行串成原文，自動翻譯。"""
        self.set_capture_enabled(True)
        self.capture_btn.finish(True)
        self.ocr_input.setPlainText("\n".join(blocks))
        if self._translating is not None:               # 前一筆翻譯回來後再送出
            self._ocr_pending = True
            return
        self._submit(self.ocr_input, self.ocr_output, True)

    def show_ocr_error(self, reason):
        self.set_capture_enabled(True)
        self.capture_btn.finish(False)
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

    def _side_requested(self, target):
        """開關圓鈕滑到 target 側：在面板正中央詢問是否切換。"""
        self._set_locked(True)
        self.confirm.ask(f"切換到{SIDE_NAMES[target]}？")

    def _set_locked(self, on):
        """確認浮層顯示期間：分頁列、引擎選單、分頁內容停用；關閉時恢復。"""
        for w in self._lockable:
            w.setEnabled(not on)

    def set_side(self, side):
        """面板改貼 side 緣；展開中立即移過去。"""
        self.side = side
        if self._width > 0:
            self._step(self._width)
        self.update()

    def _animation_toggled(self, on):
        self.animated = on
        for b in self.loading_btns:
            b.animated = on
        self.side_switch.animated = on
        self.confirm.animated = on
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

    def _listen(self, page, text, btn):
        """page 頁（分頁編號）按了聆聽鈕 btn。btn 顯示 ✓ 或 ⏹ 時：送出 listen_stop_requested 並換回 🔊。
        其他時候：前一顆聆聽鈕換回 🔊，btn 進入 loading，記下來源頁與按鈕，送出 listen_requested。"""
        if btn is self._listen_btn and btn.state in ("done", "playing"):
            self.listen_stop_requested.emit()
            btn.ended()
            return
        if self._listen_btn is not None:
            self._listen_btn.finish(False)
            self._listen_btn.ended()
        self._listen_page = page
        self._listen_btn = btn
        btn.start_loading()
        self.listen_requested.emit(text)

    def listen_started(self):
        """語音開始播放：聆聽鈕顯示 ✓。"""
        if self._listen_btn is not None:
            self._listen_btn.finish(True)

    def listen_failed(self):
        """聆聽失敗：聆聽鈕換回 🔊。"""
        if self._listen_btn is not None:
            self._listen_btn.finish(False)
            self._listen_btn.ended()

    def listen_ended(self):
        """語音播放結束：聆聽鈕的 ✓ 或 ⏹ 換回 🔊。"""
        if self._listen_btn is not None:
            self._listen_btn.ended()

    def _clear(self, page, edit, output):
        """清除鈕：清空 page 頁（分頁編號）的原文框 edit 與譯文框 output；
        最近一次聆聽來自這一頁時送出 listen_stop_requested。"""
        edit.clear()
        output.clear()
        if self._listen_page == page:
            self.listen_stop_requested.emit()
            self.listen_failed()

    def _clear_text(self):
        """文字翻譯頁的清除鈕：清空原文、譯文與拼音。"""
        self._clear(0, self.input, self.output)
        self.roman.set_roman("")

    def _clear_ocr(self):
        """OCR 頁的清除鈕：清空原文、譯文與拼音。"""
        self._clear(1, self.ocr_input, self.ocr_output)
        self.ocr_roman.set_roman("")

    def _submit(self, edit, output, by_line):
        text = edit.toPlainText().strip()
        if text and self._translating is None:          # 翻譯中不重複送出（兩頁一次只翻一筆）
            self._translating = self.translate_btn if output is self.output else self.ocr_translate_btn
            self._translating.start_loading()
            self.translate_btn.setEnabled(False)
            self.ocr_translate_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)            # 翻譯進行中不清除
            self.ocr_clear_btn.setEnabled(False)
            self._target_output = output
            self.translate_requested.emit(text, by_line)

    def show_result(self, result, roman=""):
        """翻譯完成（UI 執行緒）：成功顯示譯文與原文的拼音 roman（空字串時隱藏拼音區），
        失敗在底部短暫顯示引擎與原因。送出那一頁的翻譯鈕成功時顯示 ✓，失敗直接換回。"""
        self._translating.finish(result.error is None)
        self._translating = None
        self.translate_btn.setEnabled(True)
        self.ocr_translate_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.ocr_clear_btn.setEnabled(True)
        if result.error is None:
            self._target_output.setPlainText(result.text)
            # 拼音顯示在送出翻譯的那一頁
            (self.roman if self._target_output is self.output else self.ocr_roman).set_roman(roman)
        else:
            self._show_status(f"{result.engine} 翻譯失敗：{result.error}")
        if self._ocr_pending:
            self._ocr_pending = False
            self._submit(self.ocr_input, self.ocr_output, True)

    def play_collapse(self):
        self.confirm.cancel()                           # 確認浮層顯示中收合時當作取消
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
        self.setGeometry(edge_x(g, self.side, self._width), g.y() + (g.height() - PANEL_H) // 2,
                         self._width, PANEL_H)
        self.inner.move(self._inner_x(), 0)            # 左側時內容貼視窗右緣，看起來從左緣滑出

    def _inner_x(self):
        return self._width - PANEL_W if self.side == "left" else 0

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape and self.confirm.is_open():   # 確認浮層顯示中：Esc 只取消浮層
            self.confirm.cancel()
            return
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
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self._inner_x(), 0, PANEL_W, PANEL_H).adjusted(0.5, 0.5, -0.5, -0.5)
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
