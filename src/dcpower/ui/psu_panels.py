"""Panel số đo V/A/W và panel cài đặt (set, preset, hẹn giờ)."""
from __future__ import annotations

from PySide6.QtCore import QTime, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMenu, QMessageBox,
                               QPushButton, QSizePolicy, QTimeEdit, QVBoxLayout, QWidget)

from .style import T

MAX_V, MAX_A = 30.0, 10.0
LIM_MAX_V, LIM_MAX_A = 32.0, 10.5


def _cap(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", "cap")
    return lbl


class FitLabel(QWidget):
    """Chữ tự co giãn vừa khít ô của nó (không bao giờ tràn/đè sang widget khác)."""

    def __init__(self, text: str = "", color: str = "strong", align=Qt.AlignRight | Qt.AlignVCenter,
                 max_px: int = 96, min_h: int = 22, ref_text: str = ""):
        """color: khóa trong bảng màu (vd 'v', 'a', 'dim') -> tự đổi theo chế độ Sáng/Tối."""
        super().__init__()
        self._text, self._color, self._align, self._max = text, color, align, max_px
        self._ref = ref_text  # chuỗi mẫu để cỡ chữ không nhảy khi số đổi độ dài
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumHeight(min_h)
        self._font_key = None  # cache cỡ chữ theo (kích thước, độ dài chuỗi)
        self._font = QFont("Consolas")
        self._font.setStyleHint(QFont.Monospace)
        self._font.setBold(True)

    def setText(self, t: str):
        if t != self._text:
            self._text = t
            self.update()

    def text(self) -> str:
        return self._text

    def set_color(self, key: str):
        if key != self._color:
            self._color = key
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        probe = max(self._text, self._ref, key=len) or " "
        key = (self.width(), self.height(), len(probe))
        if key != self._font_key:  # chỉ đo lại font khi kích thước/độ dài thay đổi
            self._font_key = key
            self._font.setPixelSize(100)
            w100 = max(1, QFontMetrics(self._font).horizontalAdvance(probe))
            px = int(min(self.height() * 0.82, (self.width() - 4) * 100 / w100, self._max))
            self._font.setPixelSize(max(8, px))
        p.setFont(self._font)
        p.setPen(QColor(T.get(self._color, self._color)))
        p.drawText(self.rect().adjusted(2, 0, -2, 0), self._align, self._text)
        p.end()


class _Readout(QWidget):
    def __init__(self, name: str, unit: str, color: str, decimals: int = 3):
        super().__init__()
        self.unit, self.color, self.decimals = unit, color, decimals
        self.big = FitLabel("--", color, ref_text=f"{0:.{decimals}f} {unit}".replace("0.", "00.", 1))
        self.small = QLabel("")
        self.small.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.small.setProperty("role", "dim")
        self.small.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.title = _cap(name)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        head = QHBoxLayout()  # tiêu đề và "Set:" chung 1 hàng -> số to có trọn phần còn lại
        head.addWidget(self.title)
        head.addWidget(self.small, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(0)
        lay.addLayout(head)
        lay.addWidget(self.big, 1)

    def set_value(self, x: float | None):
        self.big.setText("--" if x is None else f"{x:.{self.decimals}f} {self.unit}")

    def set_sub(self, text: str):
        self.small.setText(text)

    def set_alarm(self, on: bool):
        self.big.set_color("warn" if on else self.color)


class ReadoutPanel(QWidget):
    reset_energy = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.r_v = _Readout("ĐIỆN ÁP", "V", "v")
        self.r_a = _Readout("DÒNG ĐIỆN", "A", "a")
        self.r_w = _Readout("CÔNG SUẤT", "W", "w", 2)
        self.lbl_energy = QLabel("0.000 mAh   0.0000 Wh   00:00:00")
        self.lbl_energy.setProperty("role", "mono")
        self.lbl_energy.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        btn_reset = QPushButton("Reset")
        btn_reset.setToolTip("Đặt lại bộ đếm mAh / Wh")
        btn_reset.clicked.connect(self.reset_energy)
        e = QHBoxLayout()
        e.addWidget(_cap("DUNG LƯỢNG"))
        e.addWidget(self.lbl_energy, 1)
        e.addWidget(btn_reset)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 6)
        lay.setSpacing(2)
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
    s.setMinimumHeight(30)
    s.setStyleSheet("font-size:16px;")
    return s


# 8 preset (M1..M8): (V, A, V limit, A limit). Mặc định lấy theo bộ nhớ M1-M8 của phần mềm gốc.
N_PRESETS = 8
DEFAULT_PRESETS = [
    (20.0, 5.0, 21.0, 6.0), (20.0, 10.0, 21.0, 10.1), (12.0, 5.0, 14.0, 6.0), (12.0, 10.0, 14.0, 10.1),
    (16.0, 6.0, 17.0, 10.2), (10.0, 2.0, 15.0, 10.2), (2.5, 5.0, 6.0, 10.2), (1.05, 6.0, 2.0, 10.2),
]


def preset_problem(v: float, a: float, vlim: float, ilim: float) -> str:
    """Máy cho đặt V > V limit (bật output sẽ báo lỗi OVP) -> app tự chặn."""
    if v > vlim:
        return f"Điện áp {v:g} V lớn hơn V limit {vlim:g} V"
    if a > ilim:
        return f"Dòng {a:g} A lớn hơn A limit {ilim:g} A"
    return ""


def normalize_presets(saved) -> list[tuple[float, float, float, float]]:
    """Đọc preset đã lưu (kể cả kiểu cũ 6 preset chỉ có V/A) -> đúng 8 preset có đủ 4 giá trị."""
    out = list(DEFAULT_PRESETS)
    for i, p in enumerate((saved or [])[:N_PRESETS]):
        try:
            p = [float(x) for x in p]
        except (TypeError, ValueError):
            continue
        if len(p) >= 4:
            out[i] = tuple(p[:4])
        elif len(p) == 2:  # preset kiểu cũ: thêm limit sát trên giá trị (giống cách đặt của bản gốc)
            v, a = p
            out[i] = (v, a, round(min(v + 1.0, LIM_MAX_V), 3), round(min(a + 0.1, LIM_MAX_A), 3))
    return out


class PresetDialog(QDialog):
    """Sửa 1 preset: V, A, V limit, A limit trong cùng 1 hộp thoại, có kiểm tra hợp lệ."""

    def __init__(self, parent, idx: int, preset):
        super().__init__(parent)
        self.setWindowTitle(f"Sửa preset M{idx + 1}")
        v, a, vl, il = preset
        self.s_v, self.s_a = _spin(MAX_V, 0.1, "V"), _spin(MAX_A, 0.01, "A")
        self.s_vl, self.s_il = _spin(LIM_MAX_V, 0.1, "V"), _spin(LIM_MAX_A, 0.01, "A")
        for s, x in ((self.s_v, v), (self.s_a, a), (self.s_vl, vl), (self.s_il, il)):
            s.setValue(x)
            s.setKeyboardTracking(True)
            s.valueChanged.connect(self._check)
        form = QFormLayout()
        form.addRow("Điện áp (Set V):", self.s_v)
        form.addRow("Dòng (Set A):", self.s_a)
        form.addRow("V limit (OVP):", self.s_vl)
        form.addRow("A limit (OCP):", self.s_il)
        self.lbl_err = QLabel("")
        self.lbl_err.setProperty("role", "alarm")
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.lbl_err)
        lay.addWidget(self.bb)
        self._check()

    def _check(self, *_):
        err = preset_problem(*self.value())
        self.lbl_err.setText(("⚠ " + err) if err else "")
        self.bb.button(QDialogButtonBox.Ok).setEnabled(not err)

    def value(self):
        return (self.s_v.value(), self.s_a.value(), self.s_vl.value(), self.s_il.value())


class SetpointPanel(QWidget):
    apply = Signal(dict)            # {"vset","iset","vlim","ilim"}
    timer_changed = Signal(bool, int)  # bật?, số giây
    presets_changed = Signal()         # để lưu ngay, không đợi tắt app

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
        g.addWidget(self.chk_autooff, 4, 0)
        g.addWidget(self.chk_beep, 4, 1)
        g.setVerticalSpacing(4)

        # Preset
        self.presets = list(DEFAULT_PRESETS)
        gb_p = QGroupBox("Preset M1–M8 (bấm để nạp · chuột phải để lưu / sửa)")
        self._preset_grid = QGridLayout(gb_p)
        self._preset_grid.setSpacing(4)
        self._preset_btns = []
        for i in range(N_PRESETS):
            b = QPushButton()
            b.setMinimumHeight(40)
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # 4 cột co giãn đều
            b.setStyleSheet("padding: 3px 4px;")
            b.clicked.connect(lambda _=False, i=i: self._load_preset(i))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda pos, i=i: self._preset_menu(i))
            self._preset_grid.addWidget(b, i // 4, i % 4)
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
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(6)
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
            # Chỉ bỏ qua khi người dùng ĐANG gõ dở trong ô; ô chỉ có focus vẫn phải theo giá trị máy,
            # nếu không lần áp dụng sau sẽ gửi số cũ xuống máy.
            if key in sp and not (s.hasFocus() and s.lineEdit().isModified()):
                s.blockSignals(True)
                s.setValue(sp[key])
                s.blockSignals(False)

    def set_presets(self, presets):
        self.presets = normalize_presets(presets)
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
        for s in (self.sp_v, self.sp_a, self.sp_vlim, self.sp_ilim):
            s.lineEdit().setModified(False)  # đã áp dụng -> lại nhận cập nhật từ máy
        self.apply.emit(self.values())

    def _emit_timer(self, *_):
        self.timer_changed.emit(self.chk_timer.isChecked(), self.timer_seconds())

    def _refresh_presets(self):
        for i, (b, (v, a, vl, il)) in enumerate(zip(self._preset_btns, self.presets)):
            b.setText(f"M{i + 1}  {v:g}V / {a:g}A\nlim {vl:g}V / {il:g}A")
            b.setToolTip(f"M{i + 1}: Set {v:g} V / {a:g} A · V limit {vl:g} V · A limit {il:g} A\n"
                         "Bấm để nạp vào máy · chuột phải để lưu giá trị hiện tại hoặc sửa")

    def _load_preset(self, i: int):
        v, a, vl, il = self.presets[i]
        err = preset_problem(v, a, vl, il)
        if err:  # phòng preset lưu từ trước bị sai
            QMessageBox.warning(self, f"Preset M{i + 1}", f"Không nạp được: {err}.")
            return
        for s, x in ((self.sp_v, v), (self.sp_a, a), (self.sp_vlim, vl), (self.sp_ilim, il)):
            s.blockSignals(True)
            s.setValue(x)
            s.blockSignals(False)
        self._emit_apply()

    def _preset_menu(self, i: int):
        m = QMenu(self)
        act_save = m.addAction(f"Lưu giá trị hiện tại vào M{i + 1}")
        act_edit = m.addAction(f"Sửa M{i + 1}...")
        act = m.exec(self.cursor().pos())
        if act == act_save:
            cur = (self.sp_v.value(), self.sp_a.value(), self.sp_vlim.value(), self.sp_ilim.value())
            err = preset_problem(*cur)
            if err:
                QMessageBox.warning(self, f"Preset M{i + 1}", f"Không lưu được: {err}.")
                return
            self.presets[i] = cur
        elif act == act_edit:
            dlg = PresetDialog(self, i, self.presets[i])
            if dlg.exec() != QDialog.Accepted:
                return
            self.presets[i] = dlg.value()
        self._refresh_presets()
        self.presets_changed.emit()
