"""Luồng giao tiếp với máy: đọc liên tục, nhận lệnh từ giao diện, tự kết nối lại."""
from __future__ import annotations

import queue
import threading
import time

from PySide6.QtCore import QObject, Signal

from ..device.spm import SPM3103
from ..device.transport import TransportError


class DeviceWorker(QObject):
    connected = Signal(str, dict, bool)      # idn, setpoints, output
    disconnected = Signal()
    status = Signal(str, str)                # text, level: ok/warn/err/info
    psu_sample = Signal(float, float, float)  # t, V, A
    dmm_sample = Signal(float, float, str)   # t, value, chức năng DMM
    output_changed = Signal(bool)
    setpoints_changed = Signal(dict)

    RECONNECT_S = 2.0
    MAX_ERRORS = 3

    def __init__(self):
        super().__init__()
        self._q: queue.Queue = queue.Queue()
        self._port: str | None = None
        self._want = False
        self._dev: SPM3103 | None = None
        self.dmm_enabled = True
        self._dmm_func = ""
        self._dmm_skip = 0
        self.interval_s = 0.0  # 0 = nhanh nhất có thể
        self._running = True
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._th.start()

    # ---------- API cho giao diện (an toàn luồng) ----------
    def connect_port(self, port: str):
        self._port, self._want = port, True

    def disconnect_port(self):
        self._want = False

    def is_connected(self) -> bool:
        return self._dev is not None

    def call(self, name: str, *args):
        """Gửi lệnh tới driver, vd call('set_voltage', 5.0)."""
        self._q.put((name, args))

    def set_output(self, on: bool):
        self._q.put(("set_output", (on,)))
        self._q.put(("_emit_output", ()))

    def apply_setpoints(self, sp: dict):
        for key, fn in (("vlim", "set_voltage_limit"), ("ilim", "set_current_limit"),
                        ("vset", "set_voltage"), ("iset", "set_current")):
            if key in sp:
                self._q.put((fn, (sp[key],)))
        self._q.put(("_emit_setpoints", ()))

    def shutdown(self):
        self._running = False
        self._want = False
        self._th.join(timeout=2)
        self._close()

    # ---------- Vòng lặp ----------
    def _close(self):
        if self._dev:
            try:
                self._dev.close()
            except Exception:  # noqa: BLE001
                pass
            self._dev = None
            self.disconnected.emit()

    def _try_connect(self) -> bool:
        try:
            self.status.emit(f"Đang kết nối {self._port}...", "info")
            dev = SPM3103(self._port)
            sp = dev.get_setpoints()
            out = dev.get_output()
        except Exception as e:  # noqa: BLE001
            self.status.emit(f"Không kết nối được: {e}", "err")
            return False
        self._dev = dev
        with self._q.mutex:
            self._q.queue.clear()
        self.connected.emit(dev.idn, sp, out)
        self.status.emit(f"Đã kết nối: {dev.idn}", "ok")
        return True

    def _run_queue(self):
        while True:
            try:
                name, args = self._q.get_nowait()
            except queue.Empty:
                return
            if name == "_emit_output":
                self.output_changed.emit(self._dev.get_output())
            elif name == "_emit_setpoints":
                self.setpoints_changed.emit(self._dev.get_setpoints())
            else:
                getattr(self._dev, name)(*args)
                if name in ("dmm_function", "dmm_range"):
                    if name == "dmm_function":
                        self._dmm_func = args[0]
                    self._dmm_skip = 1  # bỏ 1 lần đo đầu sau khi đổi thang

    def _loop(self):
        errors = 0
        last_try = 0.0
        last_out_poll = 0.0
        while self._running:
            if not self._want:
                if self._dev:
                    self._close()
                    self.status.emit("Đã ngắt kết nối", "info")
                time.sleep(0.05)
                continue
            if not self._dev:
                if time.monotonic() - last_try >= self.RECONNECT_S:
                    last_try = time.monotonic()
                    self._try_connect()
                    errors = 0
                time.sleep(0.05)
                continue
            t_start = time.monotonic()
            try:
                self._run_queue()
                v, a = self._dev.measure()
                self.psu_sample.emit(time.time(), v, a)
                if self.dmm_enabled:
                    val = self._dev.dmm_measure()
                    if self._dmm_skip:
                        self._dmm_skip -= 1
                    else:
                        self.dmm_sample.emit(time.time(), val, self._dmm_func)
                if t_start - last_out_poll > 1.0:  # đồng bộ khi bấm nút trên máy
                    last_out_poll = t_start
                    self.output_changed.emit(self._dev.get_output())
                errors = 0
            except (TransportError, OSError) as e:
                errors += 1
                if errors >= self.MAX_ERRORS:
                    self._close()
                    last_try = time.monotonic()
                    self.status.emit(f"Mất kết nối ({e}). Đang thử lại...", "warn")
            except Exception as e:  # noqa: BLE001
                self.status.emit(f"Lỗi: {e}", "err")
            wait = self.interval_s - (time.monotonic() - t_start)
            if wait > 0:
                time.sleep(wait)
