import math
from PySide6.QtCore import Qt, QTimer, QRectF, QPoint
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPainterPath, QLinearGradient
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame

CYAN = QColor("#49f6ff")
GREEN = QColor("#00ff9c")
DIM = QColor("#3d6a5f")
BG = QColor(6, 14, 12, 235)

ICONS = {
    "mic": "\U0001F3A4",     # 🎤
    "speech": "\U0001F4AC",  # 💬
    "ai": "\U0001F9E0",      # 🧠
    "voice": "\U0001F50A",   # 🔊
    "server": "\U0001F310",  # 🌐
    "platform": "\U0001F5A5",  # 🖥
    "clock": "\U0000231A",   # ⌚
    "prompt": ">_",
}


def label(text, size=11, color="#73ffc5", bold=True, mono=True):
    x = QLabel(text)
    f = QFont("Consolas" if mono else "Segoe UI", size)
    f.setBold(bold)
    x.setFont(f)
    x.setStyleSheet(f"color:{color}; background:transparent;")
    return x


def _chamfered_path(rect, cut=18, corner="top-right"):
    """Sci-fi frame with ONE corner cut (matches the reference HUD, which
    only clips the top-right corner of its outer panel)."""
    p = QPainterPath()
    r = rect
    if corner == "top-right":
        p.moveTo(r.left(), r.top())
        p.lineTo(r.right() - cut, r.top())
        p.lineTo(r.right(), r.top() + cut)
        p.lineTo(r.right(), r.bottom())
        p.lineTo(r.left(), r.bottom())
        p.closeSubpath()
    else:  # bottom-right (used elsewhere)
        p.moveTo(r.left(), r.top())
        p.lineTo(r.right(), r.top())
        p.lineTo(r.right(), r.bottom() - cut)
        p.lineTo(r.right() - cut, r.bottom())
        p.lineTo(r.left(), r.bottom())
        p.closeSubpath()
    return p


class HudPanel(QFrame):
    """A single framed sci-fi panel. Unlike separate boxed widgets, this
    is meant to hold MULTIPLE titled sections (via add_section) inside
    one continuous border, matching the reference: one outer frame,
    several "SYSTEM STATUS / ENVIRONMENT / ..." sections stacked inside
    it with just a thin rule under each heading."""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        if title:
            outer.addWidget(label(title, 12, "#8bfff0"))
            outer.addWidget(self._rule())

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body)

    def _rule(self):
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#0e5a49;")
        return line

    def add_section(self, title):
        """Add a heading + rule for a new section, returns a QVBoxLayout
        to add rows into — keeps everything inside the same outer frame."""
        self.body.addWidget(label(title, 11, "#8bfff0"))
        self.body.addWidget(self._rule())
        section = QVBoxLayout()
        section.setSpacing(6)
        self.body.addLayout(section)
        return section

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        path = _chamfered_path(rect, 18, "top-right")
        p.fillPath(path, QBrush(BG))
        p.setPen(QPen(QColor("#0fdca0"), 1.4))
        p.drawPath(path)
        super().paintEvent(event)


class StatusRow(QWidget):
    """One line like  🎤 MICROPHONE ........ ON"""

    def __init__(self, name, value="—", ok=True, icon="mic"):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.icon = QLabel(ICONS.get(icon, "•"))
        self.icon.setFixedWidth(20)
        self.icon.setStyleSheet("color:#49f6ff; background:transparent;")
        self.name = label(name, 10, "#79e6cf")
        self.value = label(value, 10, "#49f6ff")
        self.value.setAlignment(Qt.AlignRight)
        lay.addWidget(self.icon)
        lay.addWidget(self.name)
        lay.addStretch()
        lay.addWidget(self.value)
        self.set_state(value, ok)

    def set_state(self, value, ok=True):
        self.value.setText(value)
        color = "#49f6ff" if ok else "#ff5c6a"
        self.value.setStyleSheet(f"color:{color}; background:transparent;")


class GlowBar(QWidget):
    """A thin minimalist progress line with a caption + numeric readout —
    a single 2px track with a brighter filled segment, matching the
    reference's slim CPU/RAM-style bars rather than a thick rounded bar."""

    def __init__(self, caption):
        super().__init__()
        self.caption = caption
        self.value = 0.0  # 0..100
        self.readout = ""
        self.setMinimumHeight(30)

    def set_value(self, pct, readout=""):
        self.value = max(0.0, min(100.0, pct))
        self.readout = readout
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        p.setPen(QColor("#79e6cf"))
        p.drawText(0, 12, self.caption)
        p.setPen(QColor("#49f6ff"))
        p.drawText(self.rect().adjusted(0, 0, -2, 0), Qt.AlignRight | Qt.AlignTop, self.readout)

        y = 22
        p.setPen(QPen(QColor(15, 90, 73), 2))
        p.drawLine(0, y, self.width(), y)

        if self.value > 0:
            w = int(self.width() * (self.value / 100.0))
            p.setPen(QPen(CYAN, 2))
            p.drawLine(0, y, w, y)


class CoreWidget(QWidget):
    """The central animated AI core: layered glowing rings (simulated
    with stacked semi-transparent strokes for a soft-glow look), a
    rotating radar sweep, drifting particles, and a status readout."""

    def __init__(self):
        super().__init__()
        self.phase = 0
        self.title = "DNS AI"
        self.subtitle = "CORE ONLINE"
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(40)

    def set_status(self, subtitle):
        self.subtitle = subtitle
        self.update()

    def _tick(self):
        self.phase = (self.phase + 3) % 360
        self.update()

    def _glow_arc(self, p, c, r, start, span, color):
        """Draw one arc as several overlapping strokes of decreasing
        width/opacity to fake a soft neon glow."""
        rectf = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        for width, alpha in ((7, 40), (4, 90), (2, 255)):
            col = QColor(color)
            col.setAlpha(alpha)
            p.setPen(QPen(col, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawArc(rectf, int(start * 16), int(span * 16))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self.rect().center()
        base_r = min(self.width(), self.height()) * 0.44  # bigger, more dominant

        # faint static rings
        p.setPen(QPen(QColor(15, 90, 73), 1))
        for i in range(5):
            r = base_r * (0.42 + i * 0.145)
            p.drawEllipse(c, int(r), int(r))

        # dotted outer ring
        p.setPen(QPen(QColor("#0fdca0"), 2, Qt.DotLine))
        r_dot = base_r * 1.02
        p.drawEllipse(c, int(r_dot), int(r_dot))

        # glowing rotating arcs (the "energy brush strokes")
        for i in range(3):
            r = base_r * (0.55 + i * 0.16)
            span = 65
            start = (self.phase * (1 + i * 0.35)) % 360
            self._glow_arc(p, c, r, start, span, GREEN if i % 2 == 0 else CYAN)

        # radar sweep line
        p.setPen(QPen(CYAN, 1.5))
        ang = math.radians(self.phase * 2 % 360)
        r = base_r * 1.1
        p.drawLine(c, c + QPoint(int(r * math.cos(ang)), int(r * math.sin(ang))))

        # small arrow indicator on the left, like the reference
        p.setPen(QPen(CYAN, 2))
        p.setBrush(QBrush(CYAN))
        ax = c.x() - int(base_r * 1.15)
        p.drawPolygon(QPoint(ax, c.y() - 8), QPoint(ax, c.y() + 8), QPoint(ax - 14, c.y()))

        # drifting particle ticks
        p.setPen(QPen(QColor("#49f6ff"), 1))
        for i in range(18):
            angle = (self.phase * 1.6 + i * 20) % 360
            rad = math.radians(angle)
            r1 = base_r * 1.18
            r2 = r1 + 9
            x1 = c.x() + int(r1 * math.cos(rad)); y1 = c.y() + int(r1 * math.sin(rad))
            x2 = c.x() + int(r2 * math.cos(rad)); y2 = c.y() + int(r2 * math.sin(rad))
            p.drawLine(x1, y1, x2, y2)

        # center readout
        p.setPen(QColor("#8bfff0"))
        p.setFont(QFont("Consolas", 22, QFont.Bold))
        p.drawText(self.rect(), Qt.AlignCenter, f"{self.title}\n\n")
        p.setPen(QColor("#49f6ff"))
        p.setFont(QFont("Consolas", 11, QFont.Bold))
        sub_rect = self.rect().adjusted(0, int(base_r * 0.4), 0, 0)
        p.drawText(sub_rect, Qt.AlignCenter, self.subtitle)
