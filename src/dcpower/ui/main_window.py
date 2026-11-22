"""Cửa sổ chính: ghép các panel dạng dock (kéo, đổi kích thước, tách rời được)."""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, Qt, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPixmap,
                           QShortcut)
from PySide6.QtWidgets import (QApplication, QColorDialog, QComboBox, QDockWidget,
                               QFileDialog, QFrame, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QScrollArea, QSizePolicy, QToolBar, QWidget)

from ..core.data import EnergyMeter
from ..core.worker import DeviceWorker
from ..device.transport import list_ports
from .chart_panel import ChartPanel
from .dmm_panel import DmmController
from .psu_panels import ReadoutPanel, SetpointPanel
from .sequence_panel import SequencePanel
from .style import THEME_NAMES, T, set_theme, theme_name

APP_NAME = "DC Power"
LOGO_EXT = (".png", ".svg", ".ico", ".jpg", ".jpeg", ".bmp")
LAYOUT_VERSION = 3
LOGO_TOOLBAR_H = 52            # chiều cao logo góc trên phải (px)
LOGO_WATERMARK_OPACITY = 0.07  # độ đậm logo chìm (0 = ẩn hẳn, 1 = rõ hẳn)
LOGO_WATERMARK_MAX = 1200      # độ phân giải giữ sẵn cho logo chìm


def app_root() -> Path:
    if getattr(sys, "frozen", False):  # chạy từ .exe
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[3]


def find_logo() -> Path | None:
    for d in (app_root() / "upload", Path(getattr(sys, "_MEIPASS", "")) / "upload"):
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in LOGO_EXT:
                    return f
    return None


class Watermark(QWidget):
    """Logo lớn rất mờ nằm đè toàn cửa sổ nhưng trong suốt với chuột -> trông như chìm dưới nền."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self._pix: QPixmap | None = None
        self._cache = None

    def set_pixmap(self, pix: QPixmap | None):
        self._pix, self._cache = pix, None
        self.update()

    def paintEvent(self, e):
        if self._pix is None:
            return
        side = int(min(self.width() * 0.6, self.height() * 0.6))
        if self._cache is None or self._cache[0] != side:
            # Nướng sẵn độ mờ vào ảnh 1 lần -> mỗi lần vẽ chỉ là chép ảnh, không phải trộn alpha lại
            src = self._pix.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            baked = QPixmap(src.size())
            baked.fill(Qt.transparent)
            bp = QPainter(baked)
            bp.setOpacity(LOGO_WATERMARK_OPACITY)
            bp.drawPixmap(0, 0, src)
            bp.end()
            self._cache = (side, baked)
        wm = self._cache[1]
        p = QPainter(self)
        p.setClipRect(e.rect())  # chỉ vẽ phần cần cập nhật
        p.drawPixmap((self.width() - wm.width()) // 2, (self.height() - wm.height()) // 2, wm)
        p.end()


def load_scaled_pixmap(path, max_side: int) -> QPixmap | None:
    """Đọc ảnh ở kích thước tối đa max_side mà không giữ bản gốc to trong RAM."""
    from PySide6.QtGui import QImageReader
    r = QImageReader(str(path))
    r.setAutoTransform(True)
    size = r.size()
    if size.isValid() and max(size.width(), size.height()) > max_side:
        r.setScaledSize(size.scaled(max_side, max_side, Qt.KeepAspectRatio))
    img = r.read()
    if img.isNull():
        return None
    return QPixmap.fromImage(img)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 760)
        self.setDockNestingEnabled(True)
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks)
        self.settings = QSettings("DCPower", "DCPower")
        self._bg_pix: QPixmap | None = None
        self._bg_cache = None
        self._logo_pix: QPixmap | None = None
        self._wm = Watermark(self)  # logo lớn mờ phủ toàn cửa sổ, không chặn chuột
        self._bg_custom: QColor | None = None  # None = màu nền theo chế độ Sáng/Tối

        self.worker = DeviceWorker()
        self.energy = EnergyMeter()
        self.sp = {"vset": 0.0, "iset": 0.0, "vlim": 32.0, "ilim": 10.5}
        self.output_on = False
        self.connected = False
        self._dev_mode = ""
        self._latest = None
        self._alarm_until = 0.0
        self._off_deadline: float | None = None
        self._rate_n, self._rate_t, self._rate = 0, time.monotonic(), 0.0

        # Panel
        self.chart = ChartPanel()
        self.readout = ReadoutPanel()
        self.setpoint = SetpointPanel()
        self.sequence = SequencePanel()
        self.dmm = DmmController()

        self.d_chart = self._dock("Đồ thị V / A", "chart", self.chart)
        self.d_read = self._dock("Số đo", "readout", self.readout)
        self.d_set = self._dock("Cài đặt nguồn", "setpoint", self.setpoint)
        self.d_seq = self._dock("Sequence", "sequence", self.sequence)
        self.d_gauge = self._dock("Đồng hồ vạn năng", "gauge", self.dmm.gauge_panel)
        self.d_dmmc = self._dock("Thang đo & Ghi giá trị", "dmmctrl", self.dmm.control_panel)

        self._build_toolbar()
        self._build_menu()
        self._wire()
        self._shortcuts()
        self.statusBar().showMessage("Chưa kết nối. Chọn cổng COM (hoặc Giả lập) rồi bấm Kết nối.")
        self.lbl_rate = QLabel("")
        self.statusBar().addPermanentWidget(self.lbl_rate)

        self._ratio_timer = QTimer(self)  # gom nhiều sự kiện resize liên tiếp thành 1 lần chia lại
        self._ratio_timer.setSingleShot(True)
        self._ratio_timer.setInterval(30)
        self._ratio_timer.timeout.connect(self._reapply_ratios)

        self._default_layout()
        self._load_settings()

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start(66)  # ~15 lần/giây cho các con số

    # ================= Dựng giao diện =================
    def _dock(self, title: str, name: str, w: QWidget) -> QDockWidget:
        d = QDockWidget(title, self)
        d.setObjectName(name)
        # Vùng cuộn: panel co giãn theo khung, khung quá nhỏ thì cuộn chứ không chặn thu nhỏ cửa sổ
        sa = QScrollArea()
        sa.setWidget(w)
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        d.setWidget(sa)
        d.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        return d

    def _default_layout(self):
        for d in (self.d_chart, self.d_read, self.d_set, self.d_seq, self.d_gauge, self.d_dmmc):
            d.setFloating(False)
            d.show()
        self.addDockWidget(Qt.LeftDockWidgetArea, self.d_chart)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.d_gauge)
        self.splitDockWidget(self.d_chart, self.d_gauge, Qt.Vertical)
        # Đồng hồ kim và bảng điều khiển của nó nằm cạnh nhau -> cửa sổ thấp hơn
        self.splitDockWidget(self.d_gauge, self.d_dmmc, Qt.Horizontal)
        self.addDockWidget(Qt.RightDockWidgetArea, self.d_read)
        self.splitDockWidget(self.d_read, self.d_set, Qt.Vertical)
        self.tabifyDockWidget(self.d_set, self.d_seq)
        self.d_set.raise_()
        QTimer.singleShot(0, self._apply_proportions)

    DEFAULT_RATIOS = {"x": 0.68, "left_y": 0.52, "gauge_x": 0.40, "right_y": 0.45}

    def _apply_proportions(self):
        if getattr(self, "_restored", False):  # lần đầu mở: giữ bố cục đã lưu, chỉ đọc tỉ lệ của nó
            self._restored = False
            self._capture_ratios()
            return
        self._ratios = dict(self.DEFAULT_RATIOS)
        self._reapply_ratios()

    # ---- Giữ tỉ lệ các panel khi đổi kích thước cửa sổ ----
    def _std_layout(self) -> bool:
        """Chỉ giữ tỉ lệ khi các panel còn ở bố cục chuẩn (người dùng chưa kéo đi chỗ khác)."""
        docks = (self.d_chart, self.d_read, self.d_set, self.d_gauge, self.d_dmmc)
        if any(d.isFloating() or not d.isVisible() for d in docks):
            return False
        L, R = Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea
        return (self.dockWidgetArea(self.d_chart) == L and self.dockWidgetArea(self.d_gauge) == L
                and self.dockWidgetArea(self.d_dmmc) == L and self.dockWidgetArea(self.d_read) == R
                and self.dockWidgetArea(self.d_set) == R
                and abs(self.d_gauge.y() - self.d_dmmc.y()) < 4)

    def _capture_ratios(self):
        if not self._std_layout():
            return
        c, r, g, m, s = (self.d_chart, self.d_read, self.d_gauge, self.d_dmmc, self.d_set)
        try:
            self._ratios = {
                "x": c.width() / (c.width() + r.width()),
                "left_y": c.height() / (c.height() + g.height()),
                "gauge_x": g.width() / (g.width() + m.width()),
                "right_y": r.height() / (r.height() + s.height()),
            }
        except ZeroDivisionError:
            pass

    def _reapply_ratios(self):
        if not self._std_layout():
            return
        q = getattr(self, "_ratios", None) or self.DEFAULT_RATIOS
        c, r, g, m, s = (self.d_chart, self.d_read, self.d_gauge, self.d_dmmc, self.d_set)
        tw, lh, rh = c.width() + r.width(), c.height() + g.height(), r.height() + s.height()
        left = int(tw * q["x"])
        self.resizeDocks([c, r], [left, tw - left], Qt.Horizontal)
        self.resizeDocks([c, g], [int(lh * q["left_y"]), int(lh * (1 - q["left_y"]))], Qt.Vertical)
        # Kích thước widget chưa cập nhật ngay sau resizeDocks -> tính theo bề rộng đích của cột trái
        gw = max(1, left - 6)  # trừ thanh chia
        self.resizeDocks([g, m, r], [int(gw * q["gauge_x"]), gw - int(gw * q["gauge_x"]), tw - left],
                         Qt.Horizontal)
        self.resizeDocks([r, s], [int(rh * q["right_y"]), int(rh * (1 - q["right_y"]))], Qt.Vertical)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.resizeEvent_watermark()
        if hasattr(self, "_ratio_timer"):
            self._ratio_timer.start()

    def showEvent(self, e):  # trước khi hiện, panel chưa có kích thước thật -> chia lại sau khi hiện
        super().showEvent(e)
        QTimer.singleShot(50, self._reapply_ratios)

    def mouseReleaseEvent(self, e):  # kéo thanh chia giữa các panel xong -> nhớ tỉ lệ mới
        super().mouseReleaseEvent(e)
        QTimer.singleShot(0, self._capture_ratios)

    def _build_toolbar(self):
        tb = QToolBar("Kết nối")
        tb.setObjectName("toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.cmb_port = QComboBox()
        self.cmb_port.setMinimumWidth(170)
        self._refresh_ports()
        btn_refresh = QPushButton("⟳")
        btn_refresh.setToolTip("Quét lại cổng COM")
        btn_refresh.clicked.connect(self._refresh_ports)
        self.btn_conn = QPushButton("Kết nối")
        self.btn_conn.setCheckable(True)
        self.btn_conn.setMinimumWidth(110)
        self.btn_conn.setToolTip("Kết nối / ngắt (F2)")
        self.btn_conn.clicked.connect(self._toggle_connect)
        self.lbl_conn = QLabel("● Chưa kết nối")
        self._conn_style("dim")
        self.btn_theme = QPushButton()
        self.btn_theme.setToolTip("Đổi chế độ Sáng / Tối (Ctrl+T)")
        self.btn_theme.clicked.connect(self._toggle_theme)

        tb.addWidget(QLabel(" Cổng: "))
        tb.addWidget(self.cmb_port)
        tb.addWidget(btn_refresh)
        tb.addWidget(self.btn_conn)
        tb.addWidget(self.lbl_conn)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(self.btn_theme)
        self.lbl_logo = QLabel()
        tb.addWidget(self.lbl_logo)
        self._load_logo()

    def _build_menu(self):
        mb = self.menuBar()
        m = mb.addMenu("Tệp")
        m.addAction("Chụp ảnh đồ thị...", self._snapshot)
        m.addSeparator()
        m.addAction("Thoát", self.close)

        m = mb.addMenu("Giao diện")
        grp = QActionGroup(self)
        self._theme_actions = {}
        for key in ("dark", "light"):
            a = QAction(f"Chế độ {THEME_NAMES[key]}", self, checkable=True)
            a.triggered.connect(lambda _=False, k=key: self.apply_theme(k))
            grp.addAction(a)
            m.addAction(a)
            self._theme_actions[key] = a
        m.addSeparator()
        m.addAction("Chọn hình nền...", self._choose_bg)
        m.addAction("Chọn màu nền...", self._choose_bg_color)
        m.addAction("Màu nền theo chế độ", self._reset_bg_color)
        m.addAction("Bỏ hình nền", lambda: self._set_bg(None))
        m.addSeparator()
        m.addAction("Tải lại logo (thư mục upload)", self._load_logo)
        m.addSeparator()
        m.addAction("Khôi phục bố cục mặc định", self._default_layout)
        m.addSeparator()
        for d in (self.d_chart, self.d_read, self.d_set, self.d_seq, self.d_gauge, self.d_dmmc):
            m.addAction(d.toggleViewAction())

        m = mb.addMenu("Trợ giúp")
        m.addAction("Phím tắt", self._show_shortcuts)
        m.addAction("Giới thiệu", lambda: QMessageBox.about(
            self, APP_NAME, f"<b>{APP_NAME}</b><br>Phần mềm điều khiển nguồn OWON SPM3103."))

    def _shortcuts(self):
        for key, fn in (("F5", self._toggle_output), ("F2", self.btn_conn.click),
                        ("F6", self.dmm.toggle_hold), ("F7", self.dmm.record),
                        ("Space", self.chart.toggle_pause),
                        ("Ctrl+S", self._snapshot), ("Ctrl+T", self._toggle_theme),
                        # Chọn nhanh chức năng đồng hồ vạn năng
                        ("Ctrl+1", lambda: self.dmm.select_func("DCV")),
                        ("Ctrl+2", lambda: self.dmm.select_func("RES")),
                        ("Ctrl+3", lambda: self.dmm.select_func("DIOD"))):
            sc = QShortcut(QKeySequence(key), self, fn)
            sc.setContext(Qt.ApplicationShortcut)  # chạy cả khi đang ở panel tách rời

    # ================= Kết nối tín hiệu =================
    def _wire(self):
        w = self.worker
        w.connected.connect(self._on_connected)
        w.disconnected.connect(self._on_disconnected)
        w.status.connect(self._on_status)
        w.psu_sample.connect(self._on_psu)
        w.psu_status.connect(self._on_psu_status)
        w.dmm_sample.connect(self.dmm.on_sample)
        w.output_changed.connect(self._on_output)
        w.setpoints_changed.connect(self._on_setpoints)

        self.chart.output_toggled.connect(self._set_output)
        self.chart.btn_snap.clicked.connect(self._snapshot)
        self.setpoint.apply.connect(self._apply_setpoints)
        self.setpoint.presets_changed.connect(
            lambda: self.settings.setValue("presets", json.dumps(self.setpoint.presets)))
        self.setpoint.timer_changed.connect(self._on_timer_changed)
        self.readout.reset_energy.connect(self.energy.reset)
        self.sequence.apply_step.connect(lambda v, a: self._apply_setpoints({**self.setpoint.values(), "vset": v, "iset": a}))
        self.sequence.request_output.connect(self._set_output)

        self.dmm.function_changed.connect(lambda k: w.call("dmm_function", k))
        self.dmm.range_changed.connect(lambda r: w.call("dmm_range", r))
        self.dmm.enabled_changed.connect(lambda on: setattr(w, "dmm_enabled", on))

    # ================= Xử lý =================
    def _refresh_ports(self):
        cur = self.cmb_port.currentText()
        self.cmb_port.clear()
        self.cmb_port.addItems(list_ports())
        i = self.cmb_port.findText(cur)
        if i >= 0:
            self.cmb_port.setCurrentIndex(i)

    def _conn_style(self, key: str):
        """key: khóa màu trong bảng màu (dim/flag/on/warn) -> đúng màu ở cả 2 chế độ."""
        self._conn_key = key
        self.lbl_conn.setStyleSheet(f"color:{T[key]}; font-weight:700; padding: 0 8px;")

    # ================= Chế độ Sáng / Tối =================
    def apply_theme(self, name: str):
        QApplication.instance().setStyleSheet(set_theme(name))
        self.chart.apply_theme()
        self._conn_style(getattr(self, "_conn_key", "dim"))
        self.sequence._highlight(self.sequence._idx if self.sequence.running else -1)
        if hasattr(self, "_theme_actions"):
            self._theme_actions[name].setChecked(True)
        other = "light" if name == "dark" else "dark"
        self.btn_theme.setText(("☀ " if other == "light" else "🌙 ") + THEME_NAMES[other])
        self.settings.setValue("theme", name)
        self.update()

    def _toggle_theme(self):
        self.apply_theme("light" if theme_name() == "dark" else "dark")

    def _reset_bg_color(self):
        self._bg_custom = None
        self.settings.setValue("bg_color", "")
        self.update()

    def _toggle_connect(self):
        if self.btn_conn.isChecked():
            port = self.cmb_port.currentText()
            if not port:
                self.btn_conn.setChecked(False)
                return
            self.worker.connect_port(port)
            self.btn_conn.setText("Ngắt")
            self.cmb_port.setEnabled(False)
            self.lbl_conn.setText("● Đang kết nối...")
            self._conn_style("flag")
        else:
            if self.sequence.running:
                self.sequence.stop()
            self.worker.disconnect_port()
            self.btn_conn.setText("Kết nối")
            self.cmb_port.setEnabled(True)
            self.lbl_conn.setText("● Chưa kết nối")
            self._conn_style("dim")

    def _on_connected(self, idn: str, sp: dict, out: bool):
        self.connected = True
        self.lbl_conn.setText("● Đã kết nối")
        self._conn_style("on")
        self.lbl_conn.setToolTip(idn)
        self._on_setpoints(sp)
        self._on_output(out)
        self.worker.call("dmm_function", self.dmm.func)

    def _on_disconnected(self):
        self.connected = False
        self._dev_mode = ""
        self.chart.set_output(False, enabled=False)
        self.chart.set_mode("--")
        if self.btn_conn.isChecked():
            self.lbl_conn.setText("● Mất kết nối - đang thử lại")
            self._conn_style("warn")

    def _on_status(self, text: str, level: str):
        self.statusBar().showMessage(text, 8000 if level != "err" else 15000)

    def _on_setpoints(self, sp: dict):
        self.sp.update(sp)
        self.setpoint.set_values(self.sp)
        self.chart.set_setpoints(self.sp["vset"], self.sp["iset"])

    def _apply_setpoints(self, sp: dict):
        self.sp.update(sp)
        self.chart.set_setpoints(self.sp["vset"], self.sp["iset"])
        self.setpoint.set_values(self.sp)
        if self.connected:
            self.worker.apply_setpoints(sp)

    def _toggle_output(self):
        if self.connected:
            self._set_output(not self.output_on)

    def _set_output(self, on: bool):
        if not self.connected:
            return
        self.worker.set_output(on)

    def _on_output(self, on: bool):
        if on and not self.output_on and self.setpoint.chk_timer.isChecked():
            self._off_deadline = time.monotonic() + self.setpoint.timer_seconds()
        if not on:
            self._off_deadline = None
            self.setpoint.set_countdown(None)
        self.output_on = on
        self.chart.set_output(on, enabled=self.connected)

    def _on_timer_changed(self, enabled: bool, seconds: int):
        if enabled and self.output_on:
            self._off_deadline = time.monotonic() + seconds
        elif not enabled:
            self._off_deadline = None
            self.setpoint.set_countdown(None)

    def _on_psu(self, t: float, v: float, a: float):
        self._latest = (v, a)
        self._rate_n += 1
        self.chart.add_sample(t, v, a)
        self.energy.add(t, v, a, self.output_on)
        self._check_protection(v, a)

    def _on_psu_status(self, st: dict):
        self._dev_mode = st.get("mode", "")
        faults = [name for key, name in (("ovp", "QUÁ ÁP (OVP)"), ("ocp", "QUÁ DÒNG (OCP)"),
                                          ("otp", "QUÁ NHIỆT (OTP)")) if st.get(key)]
        if faults:
            msg = "⚠ MÁY BÁO: " + ", ".join(faults)
            self.chart.set_alarm(msg)
            self._alarm_until = time.monotonic() + 3600  # giữ cảnh báo tới khi máy hết báo
            self.statusBar().showMessage(msg, 15000)
            if self.setpoint.chk_beep.isChecked():
                QApplication.beep()
        elif self._alarm_until > time.monotonic() + 60:
            self._alarm_until = time.monotonic()  # máy hết báo lỗi -> xóa cảnh báo

    def _check_protection(self, v: float, a: float):
        msgs = []
        if v > self.sp["vlim"]:
            msgs.append(f"⚠ QUÁ ÁP {v:.3f} V > {self.sp['vlim']:.3f} V")
        if a > self.sp["ilim"]:
            msgs.append(f"⚠ QUÁ DÒNG {a:.3f} A > {self.sp['ilim']:.3f} A")
        if not msgs:
            return
        now = time.monotonic()
        if now < self._alarm_until:
            return
        self._alarm_until = now + 1.0
        self.chart.set_alarm("   ".join(msgs))
        self.readout.r_v.set_alarm(v > self.sp["vlim"])
        self.readout.r_a.set_alarm(a > self.sp["ilim"])
        if self.setpoint.chk_beep.isChecked():
            QApplication.beep()
        if self.setpoint.chk_autooff.isChecked() and self.output_on:
            if self.sequence.running:
                self.sequence.stop()
            self._set_output(False)
            self.statusBar().showMessage("Đã tự tắt output do vượt ngưỡng bảo vệ", 15000)

    def _refresh_ui(self):
        now = time.monotonic()
        if now - self._rate_t >= 1.0:
            self._rate = self._rate_n / (now - self._rate_t)
            self._rate_n, self._rate_t = 0, now
            self.lbl_rate.setText(f"{self._rate:.1f} mẫu/s" if self.connected else "")
        if self._alarm_until and now > self._alarm_until + 2:
            self._alarm_until = 0.0
            self.chart.set_alarm("")
            self.readout.r_v.set_alarm(False)
            self.readout.r_a.set_alarm(False)

        if self._latest and self.connected:
            v, a = self._latest
            self.readout.update_values(v, a, self.sp["vset"], self.sp["iset"])
            if self._dev_mode:  # trạng thái thật từ máy (MEASure:ALL:INFO?)
                self.chart.set_mode(self._dev_mode if self.output_on or self._dev_mode == "LỖI" else "OFF")
            elif self.output_on:
                cc = a >= self.sp["iset"] * 0.98 and v < self.sp["vset"] * 0.98
                self.chart.set_mode("CC" if cc else "CV")
            else:
                self.chart.set_mode("OFF")
        elif not self.connected:
            self.readout.update_values(None, None, self.sp["vset"], self.sp["iset"])
        self.readout.update_energy(self.energy.mah, self.energy.wh, self.energy.seconds)

        if self._off_deadline is not None:
            left = self._off_deadline - now
            self.setpoint.set_countdown(max(0, int(left + 0.999)))
            if left <= 0:
                self._off_deadline = None
                self._set_output(False)
                self.statusBar().showMessage("Hẹn giờ: đã tắt output", 15000)

    def _snapshot(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu ảnh đồ thị", f"dothi_{dt.datetime.now():%Y%m%d_%H%M%S}.png", "PNG (*.png)")
        if path:
            self.chart.snapshot(path)
            self.statusBar().showMessage(f"Đã lưu ảnh: {path}", 8000)

    def _show_shortcuts(self):
        QMessageBox.information(self, "Phím tắt", (
            "F5\tBật/tắt Output\nF2\tKết nối / Ngắt\nF6\tHold đồng hồ vạn năng\n"
            "F7\tGhi giá trị đồng hồ vạn năng\nSpace\tTạm dừng đồ thị\n"
            "Ctrl+S\tChụp ảnh đồ thị\nCtrl+T\tĐổi chế độ Sáng / Tối\n"
            "Ctrl+1\tĐồng hồ: DC V\nCtrl+2\tĐồng hồ: Điện trở\nCtrl+3\tĐồng hồ: Diode\n\nKéo tiêu đề panel để di chuyển, kéo mép để đổi kích thước,\n"
            "bấm đúp tiêu đề để tách rời panel."))

    # ================= Logo & hình nền =================
    def _load_logo(self):
        p = find_logo()
        if not p:
            self.lbl_logo.clear()
            self._logo_pix = None
            self._wm.set_pixmap(None)
            return
        # Ảnh gốc có thể rất lớn (vd 7558x5669 = ~170 MB khi giải nén) -> đọc thẳng ở cỡ nhỏ,
        # chỉ giữ các bản thu nhỏ cần dùng, không giữ ảnh gốc trong RAM.
        pix = load_scaled_pixmap(p, LOGO_WATERMARK_MAX)
        if pix is None:
            return
        icon = QIcon(pix.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setWindowIcon(icon)
        QApplication.instance().setWindowIcon(icon)
        self._logo_pix = pix  # bản dùng cho logo chìm
        self._wm.set_pixmap(self._logo_pix)
        self.lbl_logo.setPixmap(pix.scaledToHeight(LOGO_TOOLBAR_H, Qt.SmoothTransformation))
        self.lbl_logo.setContentsMargins(0, 0, 8, 0)

    def _choose_bg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn hình nền", "", "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self._set_bg(path)

    def _choose_bg_color(self):
        c = QColorDialog.getColor(self._bg_custom or QColor(T["bg"]), self, "Màu nền")
        if c.isValid():
            self._bg_custom = c
            self.settings.setValue("bg_color", c.name())
            self.update()

    def _set_bg(self, path: str | None):
        self._bg_pix = load_scaled_pixmap(path, 2560) if path else None
        self._bg_cache = None
        self.settings.setValue("bg_image", path or "")
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(e.rect(), self._bg_custom or QColor(T["bg"]))
        if self._bg_pix:
            # Co giãn ảnh nền 1 lần cho mỗi kích thước cửa sổ, không phải mỗi lần vẽ lại
            if self._bg_cache is None or self._bg_cache[0] != self.size():
                self._bg_cache = (self.size(), self._bg_pix.scaled(
                    self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            scaled = self._bg_cache[1]
            p.drawPixmap((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled)
        p.end()

    def resizeEvent_watermark(self):
        if hasattr(self, "_wm"):
            self._wm.setGeometry(self.rect())
            self._wm.raise_()

    # ================= Lưu / nạp cấu hình =================
    def _load_settings(self):
        s = self.settings
        same_layout = int(s.value("layout_version", 0)) == LAYOUT_VERSION
        geo = s.value("geometry")
        if isinstance(geo, QByteArray) and same_layout:
            self.restoreGeometry(geo)
        state = s.value("state")
        if isinstance(state, QByteArray) and same_layout:
            self._restored = self.restoreState(state)
        bgc = s.value("bg_color", "")
        # "#14161a" là màu mặc định cũ được lưu tự động -> coi như theo chế độ
        self._bg_custom = QColor(bgc) if bgc and bgc.lower() != "#14161a" else None
        self.apply_theme(s.value("theme", "dark"))
        bg = s.value("bg_image", "")
        if bg and Path(bg).exists():
            self._set_bg(bg)
        port = s.value("port", "")
        i = self.cmb_port.findText(port)
        if i >= 0:
            self.cmb_port.setCurrentIndex(i)
        try:
            sp = json.loads(s.value("setpoints", "{}"))
            self.sp.update({k: float(v) for k, v in sp.items() if k in self.sp})
            self.setpoint.set_values(self.sp)
            self.chart.set_setpoints(self.sp["vset"], self.sp["iset"])
            self.setpoint.set_presets(json.loads(s.value("presets", "[]")))
        except (ValueError, TypeError):
            pass
        self.setpoint.chk_autooff.setChecked(s.value("autooff", "true") == "true")
        self.setpoint.chk_beep.setChecked(s.value("beep", "true") == "true")

    def _save_settings(self):
        s = self.settings
        s.setValue("geometry", self.saveGeometry())
        s.setValue("state", self.saveState())
        s.setValue("layout_version", LAYOUT_VERSION)
        s.setValue("port", self.cmb_port.currentText())
        s.setValue("setpoints", json.dumps(self.setpoint.values()))
        s.setValue("presets", json.dumps(self.setpoint.presets))
        s.setValue("autooff", "true" if self.setpoint.chk_autooff.isChecked() else "false")
        s.setValue("beep", "true" if self.setpoint.chk_beep.isChecked() else "false")

    def closeEvent(self, e):
        self._save_settings()
        self.worker.shutdown()
        super().closeEvent(e)
