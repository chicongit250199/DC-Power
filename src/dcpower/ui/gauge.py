"""Đồng hồ kim (analog) có số ở giữa."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


def nice_ceil(x: float) -> float:
    """Làm tròn lên thang đẹp: 1, 2, 2.5, 5, 10 x 10^n."""
    if x <= 0 or not math.isfinite(x):
        return 1.0
    e = math.floor(math.log10(x))
    for m in (1, 2, 2.5, 5, 10):
        if m * 10 ** e >= x:
            return m * 10 ** e
    return 10 ** (e + 1)


class AnalogGauge(QWidget):
    START, SPAN = 225.0, 270.0  # độ, theo chiều kim đồng hồ từ góc trái dưới

    def __init__(self):
        super().__init__()
        self.setMinimumSize(220, 200)
        self.full_scale = 10.0
        self.scale_label = ""
        self.value = 0.0
        self._shown = 0.0
        self.text = "--"
        self.sub = ""
        self.unit = ""
        self.accent = QColor("#3dd6a3")
        self.alarm = False
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._step)
        self._anim.start(16)

    def set_reading(self, value: float, text: str, sub: str = ""):
        self.value = value if math.isfinite(value) else self.full_scale * 1.05
        self.text, self.sub = text, sub
        self.update()

    def set_scale(self, full_scale: float, label: str = ""):
        self.full_scale = full_scale
        self.scale_label = label
        self.update()

    def _step(self):  # kim chạy mượt
        target = max(-0.02, min(1.05, abs(self.value) / self.full_scale if self.full_scale else 0))
        if abs(target - self._shown) > 0.0005:
            self._shown += (target - self._shown) * 0.35
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height() * 1.12)
        r = side / 2 - 10
        c = QPointF(self.width() / 2, self.height() / 2 + r * 0.08)

        # Mặt đồng hồ
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(16, 18, 22, 230))
        p.drawEllipse(c, r, r)

        # Cung thang đo
        arc = QRectF(c.x() - r * 0.86, c.y() - r * 0.86, r * 1.72, r * 1.72)
        p.setPen(QPen(QColor("#2a2e36"), r * 0.07, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(arc, int(self.START * 16), int(-self.SPAN * 16))
        p.setPen(QPen(QColor("#e5484d"), r * 0.07, Qt.SolidLine, Qt.FlatCap))
        red = self.SPAN * 0.1  # 10% cuối màu đỏ
        p.drawArc(arc, int((self.START - self.SPAN) * 16), int(red * 16))
        p.setPen(QPen(QColor("#e5484d" if self.alarm else self.accent), r * 0.07, Qt.SolidLine, Qt.FlatCap))
        frac = max(0.0, min(1.0, self._shown))
        p.drawArc(arc, int(self.START * 16), int(-self.SPAN * frac * 16))

        # Vạch chia
        font = QFont(self.font())
        font.setPixelSize(max(9, int(r * 0.085)))
        p.setFont(font)
        for i in range(51):
            f = i / 50
            ang = math.radians(self.START - self.SPAN * f)
            major = i % 10 == 0
            r1 = r * (0.74 if major else 0.78)
            r2 = r * 0.80
            p.setPen(QPen(QColor("#c9ced6" if major else "#5a616d"), 2 if major else 1))
            p.drawLine(QPointF(c.x() + r1 * math.cos(ang), c.y() - r1 * math.sin(ang)),
                       QPointF(c.x() + r2 * math.cos(ang), c.y() - r2 * math.sin(ang)))
            if major:
                val = self.full_scale * f
                txt = f"{val:g}" if val < 1000 else f"{val / 1000:g}k"
                rt = r * 0.62
                pt = QPointF(c.x() + rt * math.cos(ang), c.y() - rt * math.sin(ang))
                p.setPen(QColor("#aab1bd"))
                p.drawText(QRectF(pt.x() - 30, pt.y() - 10, 60, 20), Qt.AlignCenter, txt)

        # Số ở giữa
        font.setPixelSize(max(14, int(r * 0.19)))
        font.setBold(True)
        font.setFamily("Consolas")
        p.setFont(font)
        p.setPen(QColor("#e5484d") if self.alarm else QColor("#f0f2f5"))
        p.drawText(QRectF(c.x() - r, c.y() + r * 0.10, 2 * r, r * 0.26), Qt.AlignCenter, self.text)
        font.setPixelSize(max(10, int(r * 0.09)))
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#8b93a1"))
        p.drawText(QRectF(c.x() - r, c.y() + r * 0.56, 2 * r, r * 0.16), Qt.AlignCenter, self.sub)
        p.drawText(QRectF(c.x() - r, c.y() - r * 0.40, 2 * r, r * 0.16), Qt.AlignCenter, self.scale_label)

        # Kim
        ang = math.radians(self.START - self.SPAN * max(-0.02, min(1.05, self._shown)))
        tip = QPointF(c.x() + r * 0.84 * math.cos(ang), c.y() - r * 0.84 * math.sin(ang))
        perp = ang + math.pi / 2
        w = r * 0.025
        base1 = QPointF(c.x() + w * math.cos(perp), c.y() - w * math.sin(perp))
        base2 = QPointF(c.x() - w * math.cos(perp), c.y() + w * math.sin(perp))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ff5d5d"))
        p.drawPolygon(QPolygonF([base1, tip, base2]))
        p.setBrush(QColor("#d7dbe2"))
        p.drawEllipse(c, r * 0.05, r * 0.05)
        p.end()
