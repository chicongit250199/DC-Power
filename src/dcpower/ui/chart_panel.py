"""Đồ thị V và A thời gian thực + nút OUTPUT to."""
from __future__ import annotations

import time

import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from ..core.data import RingBuffer
from .style import COLOR_A, COLOR_ON, COLOR_OFF, COLOR_V, COLOR_WARN, output_button_qss

WINDOWS = [("10 giây", 10), ("30 giây", 30), ("1 phút", 60), ("5 phút", 300),
           ("10 phút", 600), ("30 phút", 1800), ("Tất cả", 0)]


class ChartPanel(QWidget):
    output_toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.buf = RingBuffer(3)  # t, V, A
        self._t0 = time.time()
        self.paused = False
        self.output_on = False

        # --- Hàng trên: nút OUTPUT + trạng thái + điều khiển đồ thị ---
        self.btn_out = QPushButton("OUTPUT OFF")
        self.btn_out.setMinimumSize(190, 58)
        self.btn_out.setCursor(Qt.PointingHandCursor)
        self.btn_out.setToolTip("Bật/tắt output (F5)")
        self.btn_out.clicked.connect(lambda: self.output_toggled.emit(not self.output_on))

        self.lbl_mode = QLabel("--")
        self.lbl_mode.setAlignment(Qt.AlignCenter)
        self.lbl_mode.setMinimumWidth(64)
        self._style_badge("--", "#3a404b")

        self.lbl_alarm = QLabel("")
        self.lbl_alarm.setStyleSheet(f"color:{COLOR_WARN}; font-weight:700; font-size:14px;")

        self.cmb_win = QComboBox()
        for name, s in WINDOWS:
            self.cmb_win.addItem(name, s)
        self.cmb_win.setCurrentIndex(2)
        self.btn_pause = QPushButton("⏸ Dừng")
        self.btn_pause.setCheckable(True)
        self.btn_pause.setToolTip("Tạm dừng đồ thị (Space)")
        self.btn_pause.toggled.connect(self._on_pause)
        self.btn_auto = QPushButton("⤢ Tự co")
        self.btn_auto.setToolTip("Tự co giãn trục")
        self.btn_auto.clicked.connect(self._auto)
        self.btn_clear = QPushButton("Xóa")
        self.btn_clear.clicked.connect(self.clear)
        self.btn_snap = QPushButton("📷 Chụp")
        self.btn_snap.setToolTip("Lưu ảnh đồ thị (Ctrl+S)")

        top = QHBoxLayout()
        top.addWidget(self.btn_out)
        top.addWidget(self.lbl_mode)
        top.addWidget(self.lbl_alarm, 1)
        top.addWidget(QLabel("Hiển thị:"))
        for w in (self.cmb_win, self.btn_pause, self.btn_auto, self.btn_clear, self.btn_snap):
            top.addWidget(w)

        # --- Đồ thị: 2 tầng dùng chung trục thời gian ---
        pg.setConfigOptions(antialias=False, background=(18, 20, 24, 0), foreground="#aab1bd")
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setBackground((14, 16, 20, 235))
        self.p_v = self.glw.addPlot(row=0, col=0)
        self.p_a = self.glw.addPlot(row=1, col=0)
        self.p_a.setXLink(self.p_v)
        for p, name, unit, color in ((self.p_v, "Điện áp", "V", COLOR_V), (self.p_a, "Dòng điện", "A", COLOR_A)):
            p.showGrid(x=True, y=True, alpha=0.18)
            p.setLabel("left", name, units=unit, color=color)
            p.getAxis("left").setWidth(64)
            p.setMenuEnabled(False)
            p.setClipToView(True)
            p.setDownsampling(auto=True, mode="peak")
        self.p_a.setLabel("bottom", "Thời gian", units="s")
        self.p_v.getAxis("bottom").setStyle(showValues=False)
        self.c_v = self.p_v.plot(pen=pg.mkPen(COLOR_V, width=2))
        self.c_a = self.p_a.plot(pen=pg.mkPen(COLOR_A, width=2))
        self.set_line = {
            "v": pg.InfiniteLine(angle=0, pen=pg.mkPen(COLOR_V, width=1, style=Qt.DashLine)),
            "a": pg.InfiniteLine(angle=0, pen=pg.mkPen(COLOR_A, width=1, style=Qt.DashLine)),
        }
        self.p_v.addItem(self.set_line["v"])
        self.p_a.addItem(self.set_line["a"])
        self._follow = True
        self.p_v.getViewBox().sigRangeChangedManually.connect(lambda *_: setattr(self, "_follow", False))
        self.p_a.getViewBox().sigRangeChangedManually.connect(lambda *_: setattr(self, "_follow", False))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addLayout(top)
        lay.addWidget(self.glw, 1)

        self.set_output(False, enabled=False)

        # Vẽ lại ~30 khung hình/giây, tách khỏi tốc độ đo
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._redraw)
        self._timer.start(33)

    # ---------- API ----------
    def add_sample(self, t: float, v: float, a: float):
        self.buf.append(t - self._t0, v, a)

    def set_setpoints(self, vset: float, iset: float):
        self.set_line["v"].setValue(vset)
        self.set_line["a"].setValue(iset)

    def set_output(self, on: bool, enabled: bool = True):
        self.output_on = on
        self.btn_out.setText("OUTPUT  ON" if on else "OUTPUT  OFF")
        self.btn_out.setStyleSheet(output_button_qss(on))
        self.btn_out.setEnabled(enabled)

    def set_mode(self, mode: str):
        color = {"CV": COLOR_ON, "CC": COLOR_OFF}.get(mode, "#3a404b")
        self._style_badge(mode, color)

    def set_alarm(self, text: str):
        self.lbl_alarm.setText(text)

    def clear(self):
        self.buf.clear()
        self._t0 = time.time()
        self._follow = True

    def toggle_pause(self):
        self.btn_pause.toggle()

    def snapshot(self, path: str):
        self.glw.grab().save(path)

    # ---------- nội bộ ----------
    def _style_badge(self, text: str, color: str):
        self.lbl_mode.setText(text)
        self.lbl_mode.setStyleSheet(
            f"background:{color}; color:white; border-radius:6px; padding:8px 10px;"
            "font-weight:800; font-size:16px;")

    def _on_pause(self, on: bool):
        self.paused = on
        self.btn_pause.setText("▶ Tiếp" if on else "⏸ Dừng")
        if not on:
            self._follow = True

    def _auto(self):
        self._follow = True
        self.p_v.enableAutoRange()
        self.p_a.enableAutoRange()

    def _redraw(self):
        if self.paused or not self.isVisible():
            return
        d = self.buf.data()
        if not len(d):
            self.c_v.setData([], [])
            self.c_a.setData([], [])
            return
        win = self.cmb_win.currentData()
        if win:
            start = d[:, 0].searchsorted(d[-1, 0] - win * 1.1)
            d = d[start:]
        self.c_v.setData(d[:, 0], d[:, 1])
        self.c_a.setData(d[:, 0], d[:, 2])
        if self._follow:
            t1 = d[-1, 0]
            t0 = t1 - win if win else d[0, 0]
            self.p_v.setXRange(t0, t1, padding=0.01)
            for p in (self.p_v, self.p_a):
                p.enableAutoRange(axis="y")
