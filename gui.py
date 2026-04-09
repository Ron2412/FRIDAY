import math
import sys

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QTimer,
    Qt,
)
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

try:
    if sys.platform == "darwin":
        from AppKit import NSApp, NSApplicationActivationPolicyAccessory
    else:
        NSApp = None
        NSApplicationActivationPolicyAccessory = None
except ImportError:
    NSApp = None
    NSApplicationActivationPolicyAccessory = None


class UltronGUI(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._drag_pos = None
        self._state = "idle"
        self._time = 0.0
        self._glow_opacity = 10.0
        self._core_scale = 0.3
        self._core_opacity = 40.0
        self._target_glow = 10.0
        self._target_core_scale = 0.28
        self._target_core_opacity = 35.0
        self._audio = 0.0

        self._hide_from_dock()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        self._collapse(immediate=True)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _hide_from_dock(self):
        app = QApplication.instance()
        if app is None or NSApp is None or NSApplicationActivationPolicyAccessory is None:
            return
        ns_app = NSApp()
        if ns_app is not None:
            ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    def _screen_geometry(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return QRect(0, 0, 160, 160)
        return screen.geometry()

    def _expanded_geometry(self):
        screen = self._screen_geometry()
        return QRect(screen.width() - 176, screen.height() - 176, 160, 160)

    def _collapsed_geometry(self):
        screen = self._screen_geometry()
        return QRect(screen.width() - 88, screen.height() - 88, 72, 72)

    def _expand(self):
        self._animate_geometry(self._expanded_geometry())

    def _collapse(self, immediate=False):
        target = self._collapsed_geometry()
        if immediate:
            self.setGeometry(target)
            return
        self._animate_geometry(target)

    def _animate_geometry(self, target: QRect):
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(320)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(self.geometry())
        anim.setEndValue(target)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _tick(self):
        self._time += 0.016

        if self._state == "listening":
            self._target_glow = 30 + 50 * self._audio
            self._target_core_scale = 0.35 + 0.45 * self._audio
            self._target_core_opacity = 55 + 80 * self._audio
        elif self._state == "thinking":
            pulse = abs(math.sin(self._time * 2.5))
            self._target_glow = 12 + 10 * pulse
            self._target_core_scale = 0.3 + 0.06 * pulse
            self._target_core_opacity = 40
        elif self._state == "speaking":
            pulse = abs(math.sin(self._time * 2.2))
            self._target_glow = 35 + 30 * abs(math.sin(self._time * 3.0))
            self._target_core_scale = 0.55 + 0.25 * pulse
            self._target_core_opacity = 90 + 40 * pulse
        else:
            breathe = math.sin(self._time * 1.2)
            self._target_glow = 10 + 6 * breathe
            self._target_core_scale = 0.28 + 0.04 * breathe
            self._target_core_opacity = 35

        self._glow_opacity += (self._target_glow - self._glow_opacity) * 0.08
        self._core_scale += (self._target_core_scale - self._core_scale) * 0.08
        self._core_opacity += (self._target_core_opacity - self._core_opacity) * 0.08
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        bubble_r = min(self.width(), self.height()) / 2.0 - 8.0

        glow_pen = QPen(
            QColor(255, 255, 255, max(0, min(255, int(self._glow_opacity)))),
            12,
        )
        painter.setPen(glow_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(
            round(cx - bubble_r - 10),
            round(cy - bubble_r - 10),
            round((bubble_r + 10) * 2),
            round((bubble_r + 10) * 2),
        )

        painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
        painter.setBrush(QColor(255, 255, 255, 30))
        painter.drawEllipse(
            round(cx - bubble_r),
            round(cy - bubble_r),
            round(bubble_r * 2),
            round(bubble_r * 2),
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 22))
        highlight_w = bubble_r * 0.55
        highlight_h = bubble_r * 0.35
        painter.drawEllipse(
            round(cx - bubble_r * 0.22 - highlight_w / 2),
            round(cy - bubble_r * 0.28 - highlight_h / 2),
            round(highlight_w),
            round(highlight_h),
        )

        core_r = bubble_r * self._core_scale
        painter.setBrush(
            QColor(255, 255, 255, max(0, min(255, int(self._core_opacity))))
        )
        painter.drawEllipse(
            round(cx - core_r),
            round(cy - core_r),
            round(core_r * 2),
            round(core_r * 2),
        )

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _e):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, _e):
        QApplication.quit()

    def set_worker(self, worker):
        self._worker = worker

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(5000)
        event.accept()

    def on_state_changed(self, state: str):
        self._state = state.lower().split()[0]
        if self._state in ("listening", "speaking"):
            self._expand()
        else:
            self._collapse()

    def on_audio_level(self, level: float):
        self._audio = max(0.0, min(1.0, level))

    def on_user_spoke(self, _text: str):
        pass

    def on_ultron_responded(self, _text: str):
        pass
