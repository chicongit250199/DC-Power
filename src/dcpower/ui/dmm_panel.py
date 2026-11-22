"""Đồng hồ vạn năng: panel kim (trái) + panel điều khiển & ghi giá trị (phải)."""
from __future__ import annotations

import collections
import csv
import datetime as dt
import math
import re
import time

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                               QFileDialog, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget, QButtonGroup)

from ..core.data import Stats, si_format
from ..device import commands as C
from .gauge import AnalogGauge, nice_ceil

_PFX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6, "G": 1e9}


def parse_range(text: str) -> float:
    m = re.match(r"([\d.]+)\s*([pnuµmkMG]?)", text)
    if not m:
        return 0.0
    return float(m.group(1)) * _PFX.get(m.group(2), 1.0)


class DmmController(QObject):
    function_changed = Signal(str)
    range_changed = Signal(str)
    enabled_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.func = "DCV"
        self.hold = False
        self.rel_offset: float | None = None
        self.stats = Stats()
        self.last_raw = math.nan
        self.last_shown = math.nan
        self._recent = collections.deque(maxlen=30)
        self._last_beep = 0.0
        self._last_auto_rec = 0.0
        self.gauge_panel = self._build_gauge()
        self.control_panel = self._build_controls()
        self._select_func("DCV")

    # ---------- dựng giao diện ----------
    def _build_gauge(self) -> QWidget:
        w = QWidget()
        w.setObjectName("Panel")
        self.gauge = AnalogGauge()
        self.lbl_stats = QLabel("")
        self.lbl_stats.setAlignment(Qt.AlignCenter)
        self.lbl_stats.setStyleSheet("font-family:Consolas,Menlo,monospace; font-size:13px; color:#aab1bd;")
        self.lbl_flags = QLabel("")
        self.lbl_flags.setAlignment(Qt.AlignCenter)
        self.lbl_flags.setStyleSheet("color:#ffb547; font-weight:800; font-size:14px;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.addWidget(self.lbl_flags)
        lay.addWidget(self.gauge, 1)
        lay.addWidget(self.lbl_stats)
        return w

    def _build_controls(self) -> QWidget:
        w = QWidget()
        w.setObjectName("Panel")
        self.chk_enable = QCheckBox("Bật đọc đồng hồ vạn năng")
        self.chk_enable.setChecked(True)
        self.chk_enable.toggled.connect(self.enabled_changed)

        grid = QGridLayout()
        self._func_group = QButtonGroup(w)
        self._func_group.setExclusive(True)
        for i, (key, (name, *_)) in enumerate(C.DMM_FUNCTIONS.items()):
            b = QPushButton(name)
            b.setCheckable(True)
            b.setMinimumHeight(38)
            b.clicked.connect(lambda _=False, k=key: self._select_func(k))
            self._func_group.addButton(b)
            b.setProperty("func", key)
            grid.addWidget(b, i // 4, i % 4)

        self.cmb_range = QComboBox()
        self.cmb_range.setMinimumHeight(32)
        self.cmb_range.currentTextChanged.connect(self._on_range)
        self.btn_hold = QPushButton("HOLD")
        self.btn_hold.setCheckable(True)
        self.btn_hold.setToolTip("Giữ giá trị (F6)")
        self.btn_hold.toggled.connect(self._on_hold)
        self.btn_rel = QPushButton("REL")
        self.btn_rel.setCheckable(True)
        self.btn_rel.setToolTip("Đo tương đối: lấy giá trị hiện tại làm mốc 0")
        self.btn_rel.toggled.connect(self._on_rel)
        btn_reset = QPushButton("Reset Min/Max")
        btn_reset.clicked.connect(self._reset_stats)
        r = QHBoxLayout()
        r.addWidget(QLabel("Thang đo:"))
        r.addWidget(self.cmb_range, 1)
        r.addWidget(self.btn_hold)
        r.addWidget(self.btn_rel)
        r.addWidget(btn_reset)

        # Ghi giá trị
        self.btn_rec = QPushButton("● Ghi giá trị")
        self.btn_rec.setToolTip("Ghi giá trị hiện tại (F7)")
        self.btn_rec.clicked.connect(self.record)
        self.chk_auto = QCheckBox("Tự ghi mỗi")
        self.sp_auto = QDoubleSpinBox()
        self.sp_auto.setRange(0.1, 3600)
        self.sp_auto.setValue(1.0)
        self.sp_auto.setSuffix(" s")
        btn_export = QPushButton("Xuất CSV")
        btn_export.clicked.connect(self._export)
        btn_clear = QPushButton("Xóa")
        btn_clear.clicked.connect(lambda: self.table.setRowCount(0))
        rr = QHBoxLayout()
        for x in (self.btn_rec, self.chk_auto, self.sp_auto):
            rr.addWidget(x)
        rr.addStretch(1)
        rr.addWidget(btn_export)
        rr.addWidget(btn_clear)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Thời gian", "Chức năng", "Giá trị"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.addWidget(self.chk_enable)
        lay.addLayout(grid)
        lay.addLayout(r)
        lay.addLayout(rr)
        lay.addWidget(self.table, 1)
        return w

    # ---------- xử lý ----------
    @property
    def unit(self) -> str:
        return C.DMM_FUNCTIONS[self.func][1]

    def _select_func(self, key: str):
        self.func = key
        for b in self._func_group.buttons():
            b.setChecked(b.property("func") == key)
        self.cmb_range.blockSignals(True)
        self.cmb_range.clear()
        self.cmb_range.addItem("AUTO")
        self.cmb_range.addItems(C.DMM_FUNCTIONS[key][3])
        self.cmb_range.setEnabled(bool(C.DMM_FUNCTIONS[key][3]))
        self.cmb_range.blockSignals(False)
        self.btn_rel.setChecked(False)
        self._reset_stats()
        self._recent.clear()
        if key == "CONT":
            self.gauge.set_scale(C.DMM["continuity_threshold_ohm"] * 10, "Ω")
        elif key == "DIOD":
            self.gauge.set_scale(2.0, "V")
        self.function_changed.emit(key)

    def _on_range(self, text: str):
        self._recent.clear()
        self.range_changed.emit(text)

    def _on_hold(self, on: bool):
        self.hold = on
        self._flags()

    def _on_rel(self, on: bool):
        self.rel_offset = self.last_raw if on and math.isfinite(self.last_raw) else None
        if on and self.rel_offset is None:
            self.btn_rel.setChecked(False)
        self._reset_stats()
        self._flags()

    def _flags(self):
        f = []
        if self.hold:
            f.append("HOLD")
        if self.rel_offset is not None:
            f.append(f"REL ({si_format(self.rel_offset, self.unit)})")
        self.lbl_flags.setText("   ".join(f))

    def _reset_stats(self):
        self.stats.reset()
        self.lbl_stats.setText("")

    def toggle_hold(self):
        self.btn_hold.toggle()

    def on_sample(self, t: float, raw: float, func: str = ""):
        if func and func != self.func:  # giá trị của chức năng cũ còn trên đường truyền
            return
        self.last_raw = raw
        if self.hold:
            return
        overload = not math.isfinite(raw) or abs(raw) > 9e36
        value = raw - self.rel_offset if (self.rel_offset is not None and not overload) else raw
        self.last_shown = math.nan if overload else value
        if not overload:
            self.stats.add(value)

        # Thang của kim
        rng = self.cmb_range.currentText()
        if self.func in ("CONT", "DIOD"):
            pass
        elif rng != "AUTO" and parse_range(rng) > 0:
            self.gauge.set_scale(parse_range(rng), rng)
        elif not overload:
            self._recent.append(abs(value))
            full = nice_ceil(max(self._recent) * 1.05)
            self.gauge.set_scale(full, f"AUTO · {si_format(full, self.unit, 3)}")

        sub = C.DMM_FUNCTIONS[self.func][0]
        self.gauge.alarm = False
        if self.func == "CONT":
            short = not overload and raw < C.DMM["continuity_threshold_ohm"]
            sub = "THÔNG MẠCH" if short else "HỞ MẠCH"
            if short and time.monotonic() - self._last_beep > 0.25:
                QApplication.beep()
                self._last_beep = time.monotonic()
        text = "OL" if overload else si_format(value, self.unit)
        self.gauge.set_reading(math.inf if overload else value, text, sub)

        if self.stats.n:
            u = self.unit
            self.lbl_stats.setText(
                f"Min {si_format(self.stats.min, u)}   Max {si_format(self.stats.max, u)}   "
                f"TB {si_format(self.stats.avg, u)}   n={self.stats.n}")

        if self.chk_auto.isChecked() and time.monotonic() - self._last_auto_rec >= self.sp_auto.value():
            self._last_auto_rec = time.monotonic()
            self.record()

    def record(self):
        if not math.isfinite(self.last_raw) and not self.hold:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        val = "OL" if not math.isfinite(self.last_shown) else si_format(self.last_shown, self.unit)
        items = [str(row + 1), dt.datetime.now().strftime("%H:%M:%S.%f")[:-3],
                 C.DMM_FUNCTIONS[self.func][0], val]
        for col, txt in enumerate(items):
            it = QTableWidgetItem(txt)
            it.setData(Qt.UserRole, self.last_shown)
            self.table.setItem(row, col, it)
        self.table.scrollToBottom()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self.control_panel, "Xuất giá trị đồng hồ vạn năng",
            f"dmm_{dt.datetime.now():%Y%m%d_%H%M%S}.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["#", "Thời gian", "Chức năng", "Giá trị", "Giá trị (số)"])
            for r in range(self.table.rowCount()):
                cells = [self.table.item(r, c).text() for c in range(4)]
                w.writerow(cells + [self.table.item(r, 3).data(Qt.UserRole)])
