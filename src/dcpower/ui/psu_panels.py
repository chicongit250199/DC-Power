"""Panel số đo V/A/W và panel cài đặt (set, preset, hẹn giờ)."""
from __future__ import annotations

from PySide6.QtCore import QTime, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QMenu, QPushButton, QTimeEdit,
                               QVBoxLayout, QWidget, QInputDialog)

from .style import COLOR_A, COLOR_V, COLOR_W, COLOR_WARN

MAX_V, MAX_A = 30.0, 10.0
LIM_MAX_V, LIM_MAX_A = 32.0, 10.5


def _cap(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", "cap")
    return lbl


class _Readout(QWidget):
    def __init__(self, name: str, unit: str, color: str, decimals: int = 3):
        super().__init__()
        self.unit, self.color, self.decimals = unit, color, decimals
        self.big = QLabel("--")
        self.big.setProperty("role", "big")
        self.big.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.small = QLabel("")
        self.small.setAlignment(Qt.AlignRight)
        self.small.setStyleSheet("color:#8b93a1; font-size:13px;")
        self.title = _cap(name)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(0)
        lay.addWidget(self.title)
        lay.addWidget(self.big)
        lay.addWidget(self.small)
        self.set_alarm(False)

    def set_value(self, x: float | None):
        self.big.setText("--" if x is None else f"{x:.{self.decimals}f} {self.unit}")

    def set_sub(self, text: str):
        self.small.setText(text)

    def set_alarm(self, on: bool):
        c = COLOR_WARN if on else self.color
        self.big.setStyleSheet(f"color:{c}; font-size:40px;")

    def resizeEvent(self, e):  # chữ to theo kích thước panel
        px = max(18, min(int(self.width() / 7.5), int(self.height() * 0.55), 72))
        c = self.big.styleSheet().split(";")[0]
        self.big.setStyleSheet(f"{c}; font-size:{px}px;")
        super().resizeEvent(e)


class ReadoutPanel(QWidget):
    reset_energy = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.r_v = _Readout("ĐIỆN ÁP", "V", COLOR_V)
        self.r_a = _Readout("DÒNG ĐIỆN", "A", COLOR_A)
        self.r_w = _Readout("CÔNG SUẤT", "W", COLOR_W, 2)
        self.lbl_energy = QLabel("0.000 mAh   0.0000 Wh   00:00:00")
        self.lbl_energy.setStyleSheet("font-family:Consolas,Menlo,monospace; font-size:14px; color:#d7dbe2;")
        btn_reset = QPushButton("Reset")
        btn_reset.setToolTip("Đặt lại bộ đếm mAh / Wh")
        btn_reset.clicked.connect(self.reset_energy)
        e = QHBoxLayout()
        e.addWidget(_cap("DUNG LƯỢNG"))
        e.addWidget(self.lbl_energy, 1)
        e.addWidget(btn_reset)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.addWidget(self.r_v, 3)
        lay.addWidget(self.r_a, 3)
        lay.addWidget(self.r_w, 2)
        lay.addLayout(e)

    def update_values(self, v, a, vset, iset):
        self.r_v.set_value(v)
        self.r_a.set_value(a)
        self.r_w.set_value(None if v is None else v * a)
        self.r_v.set_sub(f"Set: {vset:.3f} V")
        self.r_a.set_sub(f"Set: {iset:.3f} A")

    def update_energy(self, mah: float, wh: float, seconds: float):
        s = int(seconds)
        self.lbl_energy.setText(f"{mah:.3f} mAh   {wh:.4f} Wh   {s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}")


def _spin(maxv: float, step: float, suffix: str) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(0, maxv)
    s.setDecimals(3)
    s.setSingleStep(step)
    s.setSuffix(f" {suffix}")
    s.setKeyboardTracking(False)
    s.setMinimumHeight(34)
    s.setStyleSheet("font-size:16px;")
    return s


DEFAULT_PRESETS = [(3.3, 1.0), (5.0, 2.0), (9.0, 1.0), (12.0, 2.0), (24.0, 1.0), (30.0, 0.5)]


class SetpointPanel(QWidget):
    apply = Signal(dict)            # {"vset","iset","vlim","ilim"}
    timer_changed = Signal(bool, int)  # bật?, số giây

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.sp_v = _spin(MAX_V, 0.1, "V")
        self.sp_a = _spin(MAX_A, 0.01, "A")
        self.sp_vlim = _spin(LIM_MAX_V, 0.1, "V")
        self.sp_ilim = _spin(LIM_MAX_A, 0.01, "A")
        self.sp_vlim.setValue(LIM_MAX_V)
        self.sp_ilim.setValue(LIM_MAX_A)
        for s in (self.sp_v, self.sp_a, self.sp_vlim, self.sp_ilim):
            s.editingFinished.connect(self._emit_apply)

        g = QGridLayout()
        g.addWidget(_cap("SET V"), 0, 0)
        g.addWidget(_cap("SET A"), 0, 1)
        g.addWidget(self.sp_v, 1, 0)
        g.addWidget(self.sp_a, 1, 1)
        g.addWidget(_cap("V LIMIT (OVP)"), 2, 0)
        g.addWidget(_cap("A LIMIT (OCP)"), 2, 1)
        g.addWidget(self.sp_vlim, 3, 0)
        g.addWidget(self.sp_ilim, 3, 1)
        self.chk_autooff = QCheckBox("Tự tắt output khi vượt ngưỡng")
        self.chk_autooff.setChecked(True)
        self.chk_beep = QCheckBox("Bíp cảnh báo")
        self.chk_beep.setChecked(True)
        g.addWidget(self.chk_autooff, 4, 0, 1, 2)
        g.addWidget(self.chk_beep, 5, 0, 1, 2)

        # Preset
        self.presets = list(DEFAULT_PRESETS)
        gb_p = QGroupBox("Preset (chuột phải để lưu giá trị hiện tại)")
        self._preset_grid = QGridLayout(gb_p)
        self._preset_btns = []
        for i in range(len(self.presets)):
            b = QPushButton()
            b.setMinimumHeight(32)
            b.clicked.connect(lambda _=False, i=i: self._load_preset(i))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda pos, i=i: self._preset_menu(i))
            self._preset_grid.addWidget(b, i // 3, i % 3)
            self._preset_btns.append(b)
        self._refresh_presets()

        # Hẹn giờ
        gb_t = QGroupBox("Hẹn giờ tắt output")
        tl = QHBoxLayout(gb_t)
        self.chk_timer = QCheckBox("Bật")
        self.time_edit = QTimeEdit(QTime(0, 5, 0))
        self.time_edit.setDisplayFormat("HH:mm:ss")
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("font-family:Consolas,Menlo,monospace; font-size:15px;")
        tl.addWidget(self.chk_timer)
        tl.addWidget(self.time_edit)
        tl.addWidget(self.lbl_count, 1)
        self.chk_timer.toggled.connect(self._emit_timer)
        self.time_edit.timeChanged.connect(self._emit_timer)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.addLayout(g)
        lay.addWidget(gb_p)
        lay.addWidget(gb_t)
        lay.addStretch(1)

    # ---------- API ----------
    def values(self) -> dict:
        return {"vset": self.sp_v.value(), "iset": self.sp_a.value(),
                "vlim": self.sp_vlim.value(), "ilim": self.sp_ilim.value()}

    def set_values(self, sp: dict):
        for key, s in (("vset", self.sp_v), ("iset", self.sp_a), ("vlim", self.sp_vlim), ("ilim", self.sp_ilim)):
            if key in sp and not s.hasFocus():
                s.blockSignals(True)
                s.setValue(sp[key])
                s.blockSignals(False)

    def set_presets(self, presets):
        if presets and len(presets) == len(self.presets):
            self.presets = [tuple(map(float, p)) for p in presets]
            self._refresh_presets()

    def set_countdown(self, seconds: int | None):
        if seconds is None:
            self.lbl_count.setText("")
        else:
            self.lbl_count.setText(f"còn {seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}")

    def timer_seconds(self) -> int:
        t = self.time_edit.time()
        return t.hour() * 3600 + t.minute() * 60 + t.second()

    # ---------- nội bộ ----------
    def _emit_apply(self):
        self.apply.emit(self.values())

    def _emit_timer(self, *_):
        self.timer_changed.emit(self.chk_timer.isChecked(), self.timer_seconds())

    def _refresh_presets(self):
        for b, (v, a) in zip(self._preset_btns, self.presets):
            b.setText(f"{v:g} V / {a:g} A")

    def _load_preset(self, i: int):
        v, a = self.presets[i]
        self.sp_v.setValue(v)
        self.sp_a.setValue(a)
        self._emit_apply()

    def _preset_menu(self, i: int):
        m = QMenu(self)
        act_save = m.addAction("Lưu giá trị hiện tại vào preset này")
        act_edit = m.addAction("Sửa preset...")
        act = m.exec(self.cursor().pos())
        if act == act_save:
            self.presets[i] = (self.sp_v.value(), self.sp_a.value())
        elif act == act_edit:
            v, ok1 = QInputDialog.getDouble(self, "Preset", "Điện áp (V):", self.presets[i][0], 0, MAX_V, 3)
            if not ok1:
                return
            a, ok2 = QInputDialog.getDouble(self, "Preset", "Dòng (A):", self.presets[i][1], 0, MAX_A, 3)
            if not ok2:
                return
            self.presets[i] = (v, a)
        self._refresh_presets()
