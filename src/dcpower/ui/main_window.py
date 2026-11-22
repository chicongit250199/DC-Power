"""Cửa sổ chính: ghép các panel dạng dock (kéo, đổi kích thước, tách rời được)."""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QColorDialog, QComboBox, QDockWidget,
                               QFileDialog, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QSizePolicy, QToolBar, QWidget)

from ..core.data import CsvLogger, EnergyMeter, log_dir
from ..core.worker import DeviceWorker
from ..device.transport import list_ports
from .chart_panel import ChartPanel
from .dmm_panel import DmmController
from .psu_panels import ReadoutPanel, SetpointPanel
from .sequence_panel import SequencePanel

APP_NAME = "DC Power"
LOGO_EXT = (".png", ".svg", ".ico", ".jpg", ".jpeg", ".bmp")
LAYOUT_VERSION = 1


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1500, 950)
        self.setDockNestingEnabled(True)
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks)
        self.settings = QSettings("DCPower", "DCPower")
        self._bg_pix: QPixmap | None = None
        self._bg_color = QColor("#14161a")

        self.worker = DeviceWorker()
        self.energy = EnergyMeter()
        self.psu_log = CsvLogger(["Thời gian", "V", "A", "W", "Output"])
        self.sp = {"vset": 0.0, "iset": 0.0, "vlim": 32.0, "ilim": 10.5}
        self.output_on = False
        self.connected = False
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

        self._default_layout()
        self._load_settings()

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start(66)  # ~15 lần/giây cho các con số

    # ================= Dựng giao diện =================
    def _dock(self, title: str, name: str, w: QWidget) -> QDockWidget:
        d = QDockWidget(title, self)
        d.setObjectName(name)
        d.setWidget(w)
        d.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        return d

    def _default_layout(self):
        for d in (self.d_chart, self.d_read, self.d_set, self.d_seq, self.d_gauge, self.d_dmmc):
            d.setFloating(False)
            d.show()
        self.addDockWidget(Qt.LeftDockWidgetArea, self.d_chart)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.d_gauge)
        self.splitDockWidget(self.d_chart, self.d_gauge, Qt.Vertical)
        self.addDockWidget(Qt.RightDockWidgetArea, self.d_read)
        self.splitDockWidget(self.d_read, self.d_set, Qt.Vertical)
        self.splitDockWidget(self.d_set, self.d_dmmc, Qt.Vertical)
        self.tabifyDockWidget(self.d_set, self.d_seq)
        self.d_set.raise_()
        QTimer.singleShot(0, self._apply_proportions)

    def _apply_proportions(self):
        w, h = self.width(), self.height()
        self.resizeDocks([self.d_chart, self.d_read], [int(w * 2 / 3), int(w / 3)], Qt.Horizontal)
        self.resizeDocks([self.d_chart, self.d_gauge], [h // 2, h // 2], Qt.Vertical)
        self.resizeDocks([self.d_read, self.d_set, self.d_dmmc], [int(h * 0.2), int(h * 0.3), h // 2], Qt.Vertical)

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
        self._conn_style("#8b93a1")
        self.btn_log = QPushButton("● Ghi log nguồn")
        self.btn_log.setCheckable(True)
        self.btn_log.setToolTip("Ghi V/A/W ra CSV (F8)")
        self.btn_log.toggled.connect(self._toggle_log)

        tb.addWidget(QLabel(" Cổng: "))
        tb.addWidget(self.cmb_port)
        tb.addWidget(btn_refresh)
        tb.addWidget(self.btn_conn)
        tb.addWidget(self.lbl_conn)
        tb.addSeparator()
        tb.addWidget(self.btn_log)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.lbl_logo = QLabel()
        tb.addWidget(self.lbl_logo)
        self._load_logo()

    def _build_menu(self):
        mb = self.menuBar()
        m = mb.addMenu("Tệp")
        m.addAction("Mở thư mục log", self._open_log_dir)
        m.addAction("Chụp ảnh đồ thị...", self._snapshot)
        m.addSeparator()
        m.addAction("Thoát", self.close)

        m = mb.addMenu("Giao diện")
        m.addAction("Chọn hình nền...", self._choose_bg)
        m.addAction("Chọn màu nền...", self._choose_bg_color)
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
                        ("F8", self.btn_log.toggle), ("Space", self.chart.toggle_pause),
                        ("Ctrl+S", self._snapshot)):
            QShortcut(QKeySequence(key), self, fn)

    # ================= Kết nối tín hiệu =================
    def _wire(self):
        w = self.worker
        w.connected.connect(self._on_connected)
        w.disconnected.connect(self._on_disconnected)
        w.status.connect(self._on_status)
        w.psu_sample.connect(self._on_psu)
        w.dmm_sample.connect(self.dmm.on_sample)
        w.output_changed.connect(self._on_output)
        w.setpoints_changed.connect(self._on_setpoints)

        self.chart.output_toggled.connect(self._set_output)
        self.chart.btn_snap.clicked.connect(self._snapshot)
        self.setpoint.apply.connect(self._apply_setpoints)
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

    def _conn_style(self, color: str):
        self.lbl_conn.setStyleSheet(f"color:{color}; font-weight:700; padding: 0 8px;")

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
            self._conn_style("#ffb547")
        else:
            if self.sequence.running:
                self.sequence.stop()
            self.worker.disconnect_port()
            self.btn_conn.setText("Kết nối")
            self.cmb_port.setEnabled(True)
            self.lbl_conn.setText("● Chưa kết nối")
            self._conn_style("#8b93a1")

    def _on_connected(self, idn: str, sp: dict, out: bool):
        self.connected = True
        self.lbl_conn.setText("● Đã kết nối")
        self._conn_style("#1db954")
        self.lbl_conn.setToolTip(idn)
        self._on_setpoints(sp)
        self._on_output(out)
        self.worker.call("dmm_function", self.dmm.func)

    def _on_disconnected(self):
        self.connected = False
        self.chart.set_output(False, enabled=False)
        self.chart.set_mode("--")
        if self.btn_conn.isChecked():
            self.lbl_conn.setText("● Mất kết nối - đang thử lại")
            self._conn_style("#ff8b3d")

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
        if self.psu_log.active:
            self.psu_log.write(t, f"{v:.4f}", f"{a:.4f}", f"{v * a:.4f}", "ON" if self.output_on else "OFF")
        self._check_protection(v, a)

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
            if self.output_on:
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

        if self.psu_log.active:
            self.btn_log.setToolTip(f"Đang ghi: {self.psu_log.path} ({self.psu_log.rows} dòng)")

    def _toggle_log(self, on: bool):
        if on:
            path = log_dir() / f"psu_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
            self.psu_log.start(path)
            self.btn_log.setText("■ Dừng ghi log")
            self.statusBar().showMessage(f"Đang ghi log: {path}", 10000)
        else:
            path, rows = self.psu_log.path, self.psu_log.rows
            self.psu_log.stop()
            self.btn_log.setText("● Ghi log nguồn")
            if path:
                self.statusBar().showMessage(f"Đã lưu {rows} dòng: {path}", 15000)

    def _open_log_dir(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        log_dir().mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir())))

    def _snapshot(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu ảnh đồ thị", f"dothi_{dt.datetime.now():%Y%m%d_%H%M%S}.png", "PNG (*.png)")
        if path:
            self.chart.snapshot(path)
            self.statusBar().showMessage(f"Đã lưu ảnh: {path}", 8000)

    def _show_shortcuts(self):
        QMessageBox.information(self, "Phím tắt", (
            "F5\tBật/tắt Output\nF2\tKết nối / Ngắt\nF6\tHold đồng hồ vạn năng\n"
            "F7\tGhi giá trị đồng hồ vạn năng\nF8\tGhi log nguồn\nSpace\tTạm dừng đồ thị\n"
            "Ctrl+S\tChụp ảnh đồ thị\n\nKéo tiêu đề panel để di chuyển, kéo mép để đổi kích thước,\n"
            "bấm đúp tiêu đề để tách rời panel."))

    # ================= Logo & hình nền =================
    def _load_logo(self):
        p = find_logo()
        if not p:
            self.lbl_logo.clear()
            return
        pix = QPixmap(str(p))
        if pix.isNull():
            return
        self.setWindowIcon(QIcon(str(p)))
        QApplication.instance().setWindowIcon(QIcon(str(p)))
        self.lbl_logo.setPixmap(pix.scaledToHeight(34, Qt.SmoothTransformation))

    def _choose_bg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn hình nền", "", "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self._set_bg(path)

    def _choose_bg_color(self):
        c = QColorDialog.getColor(self._bg_color, self, "Màu nền")
        if c.isValid():
            self._bg_color = c
            self.settings.setValue("bg_color", c.name())
            self.update()

    def _set_bg(self, path: str | None):
        self._bg_pix = QPixmap(path) if path else None
        if self._bg_pix is not None and self._bg_pix.isNull():
            self._bg_pix = None
        self.settings.setValue("bg_image", path or "")
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), self._bg_color)
        if self._bg_pix:
            scaled = self._bg_pix.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        p.end()

    # ================= Lưu / nạp cấu hình =================
    def _load_settings(self):
        s = self.settings
        geo = s.value("geometry")
        if isinstance(geo, QByteArray):
            self.restoreGeometry(geo)
        state = s.value("state")
        if isinstance(state, QByteArray) and int(s.value("layout_version", 0)) == LAYOUT_VERSION:
            self.restoreState(state)
        self._bg_color = QColor(s.value("bg_color", "#14161a"))
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
        self.psu_log.stop()
        self.worker.shutdown()
        super().closeEvent(e)
