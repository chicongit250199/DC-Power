"""Đồ thị V và A thời gian thực + nút OUTPUT to."""
from __future__ import annotations

import time

import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from ..core.data import RingBuffer
from .style import T, output_button_qss

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
        self._dirty = False

        # --- Hàng trên: nút OUTPUT + trạng thái + điều khiển đồ thị ---
        self.btn_out = QPushButton("OUTPUT OFF")
        self.btn_out.setMinimumSize(190, 58)
        self.btn_out.setCursor(Qt.PointingHandCursor)
        self.btn_out.setToolTip("Bật/tắt output (F5)")
        self.btn_out.clicked.connect(lambda: self.output_toggled.emit(not self.output_on))

        self.lbl_mode = QLabel("--")
        self.lbl_mode.setAlignment(Qt.AlignCenter)
        self.lbl_mode.setMinimumWidth(64)
        self._badge = None
        self._out_state = None
        self._mode = "--"

        self.lbl_alarm = QLabel("")
        self.lbl_alarm.setProperty("role", "alarm")

        self.cmb_win = QComboBox()
        for name, s in WINDOWS:
            self.cmb_win.addItem(name, s)
        self.cmb_win.setCurrentIndex(2)
        self.cmb_win.currentIndexChanged.connect(lambda *_: setattr(self, "_dirty", True))
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

        # --- Đồ thị: 1 khung, 2 đường. Trục V bên trái, trục A bên phải ---
        pg.setConfigOptions(antialias=False)
        self.glw = pg.GraphicsLayoutWidget()
        self.p_v = self.glw.addPlot(row=0, col=0)
        p = self.p_v
        p.setMenuEnabled(False)
        p.getAxis("left").setWidth(62)
        p.showAxis("right")
        p.getAxis("right").setWidth(62)
        # ViewBox thứ 2 cho dòng điện, dùng chung trục thời gian
        self.vb_a = pg.ViewBox()
        self.vb_a.setMenuEnabled(False)
        p.scene().addItem(self.vb_a)
        p.getAxis("right").linkToView(self.vb_a)
        self.vb_a.setXLink(p)
        p.getViewBox().sigResized.connect(self._sync_views)
        self.p_a = self.vb_a  # giữ tên cũ cho phần còn lại

        self.legend = p.addLegend(offset=(10, 6))
        self.c_v = p.plot(name="Điện áp (V)")
        # Đường dòng: vẽ đúng từng mẫu đo, không làm mượt
        self.c_a = pg.PlotDataItem()
        self.vb_a.addItem(self.c_a)
        self.legend.addItem(self.c_a, "Dòng điện (A)")
        for c in (self.c_v, self.c_a):
            c.setClipToView(True)
            c.setDownsampling(auto=True, method="peak")  # giữ đỉnh -> không mất xung ngắn
        self.set_line = {"v": pg.InfiniteLine(angle=0), "a": pg.InfiniteLine(angle=0)}
        p.addItem(self.set_line["v"], ignoreBounds=True)
        self.vb_a.addItem(self.set_line["a"], ignoreBounds=True)
        self._follow = True
        p.getViewBox().sigRangeChangedManually.connect(lambda *_: setattr(self, "_follow", False))
        self.vb_a.sigRangeChangedManually.connect(lambda *_: setattr(self, "_follow", False))

        # Thống kê dòng trong khoảng đang hiển thị (đơn vị mA)
        self.lbl_istat = QLabel("")
        self.lbl_istat.setProperty("role", "istat")
        self.lbl_istat.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addLayout(top)
        lay.addWidget(self.glw, 1)
        lay.addWidget(self.lbl_istat)

        self.apply_theme()
        self.set_output(False, enabled=False)

        # Vẽ lại ~20 khung hình/giây (đủ mượt), tách khỏi tốc độ đo; dữ liệu vẫn đủ từng mẫu
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._redraw)
        self._timer.start(50)

    # ---------- API ----------
    def add_sample(self, t: float, v: float, a: float):
        self.buf.append(t - self._t0, v, a)
        self._dirty = True

    def set_setpoints(self, vset: float, iset: float):
        self.set_line["v"].setValue(vset)
        self.set_line["a"].setValue(iset)

    def apply_theme(self):
        """Áp màu theo chế độ Sáng/Tối hiện tại cho toàn bộ đồ thị."""
        p = self.p_v
        self.glw.setBackground(T["chart_bg"])
        fg = pg.mkPen(T["chart_fg"])
        for name in ("left", "right", "bottom"):
            ax = p.getAxis(name)
            ax.setPen(fg)
        p.getAxis("left").setTextPen(T["v"])
        p.getAxis("right").setTextPen(T["a"])
        p.getAxis("bottom").setTextPen(T["chart_fg"])
        p.setLabel("left", "Điện áp", units="V", color=T["v"])
        p.setLabel("right", "Dòng điện", units="A", color=T["a"])
        p.setLabel("bottom", "Thời gian", units="s", color=T["chart_fg"])
        p.showGrid(x=True, y=True, alpha=T["grid_alpha"])
        self.c_v.setPen(pg.mkPen(T["v"], width=2))
        self.c_a.setPen(pg.mkPen(T["a"], width=2))
        self.set_line["v"].setPen(pg.mkPen(T["v"], width=1, style=Qt.DashLine))
        self.set_line["a"].setPen(pg.mkPen(T["a"], width=1, style=Qt.DashLine))
        self.legend.setLabelTextColor(T["text"])
        self.legend.setBrush(pg.mkBrush(T["chart_bg"][:3] + (200,)))
        self.legend.setPen(pg.mkPen(T["line"]))
        for _, label in self.legend.items:  # chữ chú thích đã tạo phải đổi màu riêng
            label.setText(label.text, color=T["text"])
        self._badge = None
        self._out_state = None
        self.set_mode(self._mode)
        self.set_output(self.output_on, self.btn_out.isEnabled())
        self._dirty = True

    def set_output(self, on: bool, enabled: bool = True):
        self.output_on = on
        self.btn_out.setEnabled(enabled)
        if self._out_state == on:  # không đổi -> khỏi đặt lại stylesheet (tốn CPU)
            return
        self._out_state = on
        self.btn_out.setText("OUTPUT  ON" if on else "OUTPUT  OFF")
        self.btn_out.setStyleSheet(output_button_qss(on))

    def set_mode(self, mode: str):
        self._mode = mode
        color = {"CV": T["on"], "CC": T["off"], "LỖI": T["warn"]}.get(mode, T["badge_idle"])
        self._style_badge(mode, color)

    def set_alarm(self, text: str):
        self.lbl_alarm.setText(text)

    def clear(self):
        self.buf.clear()
        self._t0 = time.time()
        self._follow = True
        self._dirty = True

    def toggle_pause(self):
        self.btn_pause.toggle()

    def snapshot(self, path: str):
        self.glw.grab().save(path)

    # ---------- nội bộ ----------
    def _style_badge(self, text: str, color: str):
        if self._badge == (text, color):  # gọi ~15 lần/giây -> chỉ đổi khi thật sự khác
            return
        self._badge = (text, color)
        self.lbl_mode.setText(text)
        self.lbl_mode.setStyleSheet(
            f"background:{color}; color:white; border-radius:6px; padding:8px 10px;"
            "font-weight:800; font-size:16px;")

    def _on_pause(self, on: bool):
        self.paused = on
        self.btn_pause.setText("▶ Tiếp" if on else "⏸ Dừng")
        if not on:
            self._follow = True
            self._dirty = True

    def _sync_views(self):
        self.vb_a.setGeometry(self.p_v.getViewBox().sceneBoundingRect())
        self.vb_a.linkedViewChanged(self.p_v.getViewBox(), self.vb_a.XAxis)

    def _auto(self):
        self._follow = True
        self.p_v.enableAutoRange()
        self.vb_a.enableAutoRange()

    def _redraw(self):
        # Không vẽ khi: tạm dừng, panel bị ẩn, cửa sổ thu nhỏ, hoặc chưa có mẫu mới
        if self.paused or not self.isVisible() or self.window().isMinimized() or not self._dirty:
            return
        self._dirty = False
        d = self.buf.data()
        # Nhiều điểm (xem "Tất cả" sau thời gian dài) -> giảm tần số vẽ để không ngốn CPU
        n_all = len(d)
        self._timer.setInterval(50 if n_all < 20_000 else 100 if n_all < 100_000 else 250)
        if not len(d):
            self.c_v.setData([], [])
            self.c_a.setData([], [])
            self.lbl_istat.setText("")
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
            self.p_v.enableAutoRange(axis="y")
            # Trục dòng bám sát dao động (tối thiểu ±2 mA) để thấy từng bước 1 mA
            a = d[:, 2]
            lo, hi = float(a.min()), float(a.max())
            pad = max((hi - lo) * 0.15, 0.002)
            self.vb_a.setYRange(lo - pad, hi + pad, padding=0)
        # Thống kê dòng trong khoảng đang xem
        a = d[:, 2]
        n = len(a)
        dt = d[-1, 0] - d[0, 0]
        rate = (n - 1) / dt if dt > 0 else 0
        self.lbl_istat.setText(
            f"I  min {a.min() * 1e3:8.1f} mA   max {a.max() * 1e3:8.1f} mA   "
            f"TB {a.mean() * 1e3:8.2f} mA   dao động {(a.max() - a.min()) * 1e3:7.1f} mA   "
            f"({n} mẫu, {rate:.0f} mẫu/s)")
