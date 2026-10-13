"""Animation utilities."""

from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QBrush

from .theme import C


def fade_in(widget, duration=200):
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    widget._fade_anim = anim


class TypingDots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 24)
        self._dots = [0.3, 0.3, 0.3]
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._phase = 0
        self._timer.start(100)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._phase = (self._phase + 1) % 15
        for i in range(3):
            p = (self._phase - i * 3) % 15
            self._dots[i] = 0.3 + 0.7 * max(0, 1 - abs(p - 3) / 3.0) if p < 7 else 0.3
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i in range(3):
            color = QColor(C.ACCENT)
            color.setAlphaF(self._dots[i])
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(6 + i * 16, 8, 6, 6)
        painter.end()


class StatusDot(QWidget):
    def __init__(self, color=C.SUCCESS, size=7, parent=None):
        super().__init__(parent)
        self._color = color
        self._size = size
        self.setFixedSize(size, size)

    def set_color(self, color):
        self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(self._color)))
        painter.drawEllipse(0, 0, self._size, self._size)
        painter.end()
