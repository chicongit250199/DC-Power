"""Sequence: chạy tự động chuỗi bước V / A / thời gian."""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .style import T

DEFAULT_STEPS = [(5.0, 1.0, 10.0), (12.0, 1.0, 20.0), (3.3, 0.5, 10.0)]


class SequencePanel(QWidget):
    apply_step = Signal(float, float)   # V, A
    request_output = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Điện áp (V)", "Dòng (A)", "Thời gian (s)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for s in DEFAULT_STEPS:
            self._add_row(*s)

        b_add = QPushButton("+ Bước")
        b_add.clicked.connect(lambda: self._add_row(5.0, 1.0, 10.0))
        b_del = QPushButton("− Xóa bước")
        b_del.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        self.sp_loop = QSpinBox()
        self.sp_loop.setRange(0, 100000)
        self.sp_loop.setValue(1)
        self.sp_loop.setSpecialValueText("∞")
        self.sp_loop.setPrefix("Lặp: ")
        self.chk_off = QCheckBox("Tắt output khi xong")
        self.chk_off.setChecked(True)
        self.btn_run = QPushButton("▶ Chạy")
        self.btn_run.clicked.connect(self.toggle)
        self.lbl = QLabel("Sẵn sàng")

        r1 = QHBoxLayout()
        for w in (b_add, b_del, self.sp_loop, self.chk_off):
            r1.addWidget(w)
        r1.addStretch(1)
        r2 = QHBoxLayout()
        r2.addWidget(self.btn_run)
        r2.addWidget(self.lbl, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.addLayout(r1)
        lay.addWidget(self.table, 1)
        lay.addLayout(r2)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.running = False

    def _add_row(self, v, a, s):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, x in enumerate((v, a, s)):
            self.table.setItem(r, c, QTableWidgetItem(f"{x:g}"))

    def steps(self) -> list[tuple[float, float, float]]:
        out = []
        for r in range(self.table.rowCount()):
            try:
                out.append(tuple(float(self.table.item(r, c).text().replace(",", ".")) for c in range(3)))
            except (AttributeError, ValueError):
                continue
        return out

    def toggle(self):
        self.stop() if self.running else self.start()

    def start(self):
        self._steps = self.steps()
        if not self._steps:
            self.lbl.setText("Chưa có bước hợp lệ")
            return
        self.running = True
        self._loop, self._idx = 1, -1
        self.btn_run.setText("■ Dừng")
        # Đặt V/A của bước 1 TRƯỚC rồi mới bật output (lệnh đi theo thứ tự hàng đợi),
        # tránh output ra theo thông số cũ trong lúc chờ.
        self._next()
        self.request_output.emit(True)
        self._timer.start(100)

    def stop(self, finished: bool = False):
        self._timer.stop()
        if self.running and (finished and self.chk_off.isChecked() or not finished):
            self.request_output.emit(False)
        self.running = False
        self.btn_run.setText("▶ Chạy")
        self.lbl.setText("Hoàn thành" if finished else "Đã dừng")
        self._highlight(-1)

    def _next(self):
        self._idx += 1
        if self._idx >= len(self._steps):
            loops = self.sp_loop.value()
            if loops and self._loop >= loops:
                self.stop(finished=True)
                return
            self._loop += 1
            self._idx = 0
        v, a, _ = self._steps[self._idx]
        self._t_step = time.monotonic()
        self.apply_step.emit(v, a)
        self._highlight(self._idx)

    def _tick(self):
        dur = self._steps[self._idx][2]
        left = dur - (time.monotonic() - self._t_step)
        loops = self.sp_loop.value() or "∞"
        self.lbl.setText(f"Bước {self._idx + 1}/{len(self._steps)} · lần {self._loop}/{loops} · còn {max(0, left):.1f}s")
        if left <= 0:
            self._next()

    def _highlight(self, row: int):
        for r in range(self.table.rowCount()):
            for c in range(3):
                it = self.table.item(r, c)
                if it:
                    it.setBackground(QColor(T["sel_row"]) if r == row else QColor(0, 0, 0, 0))
