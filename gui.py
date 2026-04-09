import math

from PyQt6.QtCore import QPropertyAnimation, QTimer, Qt, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QLabel,
    QMainWindow,
    QWidget,
)


class DragSurface(QWidget):
    def mousePressEvent(self, event):
        parent = self.window()
        if parent is not None:
            parent.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        parent = self.window()
        if parent is not None:
            parent.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        parent = self.window()
        if parent is not None:
            parent.mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        parent = self.window()
        if parent is not None:
            parent.mouseDoubleClickEvent(event)


class CloseButton(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, _event):
        self._hovered = True
        self.update()

    def leaveEvent(self, _event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QApplication.quit()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(255, 255, 255, 160 if self._hovered else 60)
        painter.setPen(QPen(color, 1.5))
        painter.drawLine(9, 9, 19, 19)
        painter.drawLine(19, 9, 9, 19)


class UltronGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._drag = None
        self._state = "idle"
        self._time = 0.0
        self._orb_r = 72.0
        self._glow_extra = 0.0
        self._core_scale = 0.25
        self._core_opacity = 60.0
        self._t_orb_r = 72.0
        self._t_glow = 0.0
        self._t_core_scale = 0.25
        self._t_core_opacity = 60.0
        self._audio = 0.0
        self._current_state_str = "idle"

        self.setFixedSize(420, 420)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._central = DragSurface(self)
        self._central.setStyleSheet("background: transparent;")
        self.setCentralWidget(self._central)

        self.lbl_state = QLabel("", self._central)
        font = QFont("SF Pro Display")
        if font.family() != "SF Pro Display":
            font = QFont("Helvetica Neue")
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Light)
        self.lbl_state.setFont(font)
        self.lbl_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_state.setStyleSheet("background: transparent; color: rgba(180, 200, 255, 160);")

        self.state_effect = QGraphicsOpacityEffect(self.lbl_state)
        self.lbl_state.setGraphicsEffect(self.state_effect)
        self.state_effect.setOpacity(0.0)
        self.state_anim = QPropertyAnimation(self.state_effect, b"opacity", self)
        self.state_anim.setDuration(200)

        self.btn_close = CloseButton(self._central)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move((geo.width() - self.width()) // 2, (geo.height() - self.height()) // 2)

    def resizeEvent(self, _event):
        self.lbl_state.setGeometry(0, 340, self.width(), 24)
        self.btn_close.move(self.width() - 40, 16)

    def _tick(self):
        self._time += 0.016

        if self._state == "listening":
            self._t_orb_r = 72 + 18 * self._audio
            self._t_glow = 8 + 22 * self._audio
            self._t_core_scale = 0.28 + 0.38 * self._audio
            self._t_core_opacity = 80 + 120 * self._audio
        elif self._state == "thinking":
            pulse = abs(math.sin(self._time * 2.8))
            self._t_orb_r = 68 + 5 * pulse
            self._t_glow = 4 + 6 * pulse
            self._t_core_scale = 0.2 + 0.08 * pulse
            self._t_core_opacity = 55
        elif self._state == "speaking":
            pulse = abs(math.sin(self._time * 2.4))
            self._t_orb_r = 78 + 12 * abs(math.sin(self._time * 2.1))
            self._t_glow = 14 + 10 * abs(math.sin(self._time * 1.8))
            self._t_core_scale = 0.42 + 0.22 * pulse
            self._t_core_opacity = 140 + 60 * pulse
        else:
            breathe = math.sin(self._time * 1.0)
            self._t_orb_r = 70 + 4 * breathe
            self._t_glow = 2 + 3 * breathe
            self._t_core_scale = 0.22
            self._t_core_opacity = 50

        spd = 0.07
        self._orb_r += (self._t_orb_r - self._orb_r) * spd
        self._glow_extra += (self._t_glow - self._glow_extra) * spd
        self._core_scale += (self._t_core_scale - self._core_scale) * spd
        self._core_opacity += (self._t_core_opacity - self._core_opacity) * spd
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(12, 12, 16, 220))
        painter.drawRoundedRect(self.rect(), 32, 32)

        cx = 210.0
        cy = 190.0
        orb_r = self._orb_r
        glow_extra = self._glow_extra

        painter.setBrush(QColor(50, 120, 255, 18))
        outer_r = orb_r + 28 + glow_extra
        painter.drawEllipse(
            round(cx - outer_r),
            round(cy - outer_r),
            round(outer_r * 2),
            round(outer_r * 2),
        )

        painter.setBrush(QColor(80, 140, 255, 35))
        mid_r = orb_r + 12 + glow_extra * 0.6
        painter.drawEllipse(
            round(cx - mid_r),
            round(cy - mid_r),
            round(mid_r * 2),
            round(mid_r * 2),
        )

        painter.setPen(QPen(QColor(160, 200, 255, 90), 1.5))
        painter.setBrush(QColor(100, 160, 255, 145))
        painter.drawEllipse(
            round(cx - orb_r),
            round(cy - orb_r),
            round(orb_r * 2),
            round(orb_r * 2),
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(220, 235, 255, 45))
        highlight_w = orb_r * 0.75
        highlight_h = orb_r * 0.45
        highlight_x = cx - orb_r * 0.2 - highlight_w / 2
        highlight_y = cy - orb_r * 0.32 - highlight_h / 2
        painter.drawEllipse(
            round(highlight_x),
            round(highlight_y),
            round(highlight_w),
            round(highlight_h),
        )

        core_r = orb_r * self._core_scale
        painter.setBrush(QColor(180, 210, 255, max(0, min(255, int(self._core_opacity)))))
        painter.drawEllipse(
            round(cx - core_r),
            round(cy - core_r),
            round(core_r * 2),
            round(core_r * 2),
        )

    def _set_state_label(self, state: str):
        if state == "listening":
            self.lbl_state.setText("Listening...")
        elif state == "thinking":
            self.lbl_state.setText("Thinking...")
        elif state == "speaking":
            self.lbl_state.setText("Speaking...")
        else:
            self.lbl_state.setText("")

        self.state_anim.stop()
        self.state_anim.setStartValue(0.0)
        self.state_anim.setEndValue(1.0 if self.lbl_state.text() else 0.0)
        self.state_anim.start()

    def _fade_out_done(self, state: str):
        self._set_state_label(state)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _event):
        self._drag = None

    def mouseDoubleClickEvent(self, _event):
        QApplication.quit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            QApplication.quit()
            return
        super().keyPressEvent(event)

    def set_worker(self, worker):
        self._worker = worker

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(5000)
        event.accept()

    @pyqtSlot(str)
    def on_state_changed(self, state: str):
        s = state.lower().split()[0]
        self._state = s
        if s == self._current_state_str:
            return

        self._current_state_str = s
        self.state_anim.stop()
        self.state_anim.setStartValue(self.state_effect.opacity())
        self.state_anim.setEndValue(0.0)
        self.state_anim.start()
        QTimer.singleShot(200, lambda: self._fade_out_done(s))

    @pyqtSlot(float)
    def on_audio_level(self, level: float):
        self._audio = max(0.0, min(1.0, level))

    @pyqtSlot(str)
    def on_user_spoke(self, _text: str):
        pass

    @pyqtSlot(str)
    def on_ultron_responded(self, _text: str):
        pass
