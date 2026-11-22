"""Driver OWON SPM3103 dựa trên bảng lệnh commands.py."""
from __future__ import annotations

import re
import time

from . import commands as C
from .transport import SimTransport, TransportError, open_transport

_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def parse_floats(text: str) -> list[float]:
    return [float(x) for x in _NUM.findall(text)]


_DMM_VAL = re.compile(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([pnuµmkKMG])?")
_PFX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3,
        "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}
# Tiền tố chức năng trong phản hồi CONFigure:ALL? -> khóa DMM_FUNCTIONS
_DMM_KEY = {f[4]: k for k, f in C.DMM_FUNCTIONS.items()}


def parse_dmm(text: str) -> tuple[float, str | None]:
    """'VOLT:DC,+000.18mV,Manual,200mV' -> (0.00018, 'DCV'); 'RES,OL,...' -> (inf, 'RES')."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        raise TransportError(f"Phản hồi DMM lạ: {text!r}")
    key = _DMM_KEY.get(parts[0].upper())
    raw = parts[1]
    m = _DMM_VAL.match(raw)
    if m:
        return float(m.group(1)) * _PFX.get(m.group(2) or "", 1.0), key
    if re.search(r"OL|OPEN", raw, re.I):
        return float("inf"), key
    raise TransportError(f"Phản hồi DMM lạ: {text!r}")


class SPM3103:
    def __init__(self, port: str):
        self.t = open_transport(port)
        self._meas_all_ok = True
        self.idn = self.t.query(C.PSU["idn"])

    def enter_remote(self):
        """Gọi SAU khi đã đồng bộ thông số (giống phần mềm gốc). Máy bận ~0.5s sau lệnh này."""
        try:
            self.t.write(C.PSU["remote"])
        except TransportError:
            return
        if not isinstance(self.t, SimTransport):
            time.sleep(0.6)

    # ---------- Nguồn ----------
    def set_voltage(self, v: float):
        self.t.write(C.PSU["set_voltage"].format(value=v))

    def set_current(self, a: float):
        self.t.write(C.PSU["set_current"].format(value=a))

    def set_voltage_limit(self, v: float):
        self.t.write(C.PSU["set_voltage_limit"].format(value=v))

    def set_current_limit(self, a: float):
        self.t.write(C.PSU["set_current_limit"].format(value=a))

    def set_output(self, on: bool):
        self.t.write(C.PSU["output_on" if on else "output_off"])

    def get_output(self) -> bool:
        r = self.t.query(C.PSU["get_output"]).upper()
        return r.startswith("ON") or r.startswith("1")

    def _qf(self, key: str) -> float:
        vals = parse_floats(self.t.query(C.PSU[key]))
        if not vals:
            raise TransportError(f"Phản hồi lạ cho {key}")
        return vals[0]

    def get_setpoints(self) -> dict:
        return {
            "vset": self._qf("get_voltage_set"),
            "iset": self._qf("get_current_set"),
            "vlim": self._qf("get_voltage_limit"),
            "ilim": self._qf("get_current_limit"),
        }

    _MODES = {"0": "STBY", "1": "CV", "2": "CC", "3": "LỖI"}

    def measure_info(self) -> tuple[float, float, dict]:
        """V, A và trạng thái thật từ máy: {'mode','ovp','ocp','otp'}. Máy cũ không hỗ trợ -> measure()."""
        if getattr(self, "_info_ok", True):
            # Lỗi đường truyền (TransportError) được ném lên để worker đếm lỗi như bình thường
            parts = [x.strip() for x in self.t.query(C.PSU["meas_info"]).split(",")]
            try:
                if len(parts) >= 7:
                    st = {"ovp": parts[3].upper() == "ON", "ocp": parts[4].upper() == "ON",
                          "otp": parts[5].upper() == "ON", "mode": self._MODES.get(parts[6], "")}
                    return float(parts[0]), float(parts[1]), st
            except ValueError:
                pass
            self._info_ok = False  # máy không hỗ trợ / định dạng lạ -> dùng MEAS:ALL?
        v, a = self.measure()
        return v, a, {}

    def measure(self) -> tuple[float, float]:
        if self._meas_all_ok:
            try:
                vals = parse_floats(self.t.query(C.PSU["meas_all"]))
                if len(vals) >= 2:
                    return vals[0], vals[1]
            except TransportError:
                pass
            self._meas_all_ok = False
        return self._qf("meas_voltage"), self._qf("meas_current")

    # ---------- Đồng hồ vạn năng ----------
    def dmm_function(self, key: str):
        self._dmm_key = key
        self.t.write(C.DMM_FUNCTIONS[key][2])

    def dmm_range(self, rng: str):
        f = C.DMM_FUNCTIONS[getattr(self, "_dmm_key", "DCV")]
        if rng == "AUTO":
            self.t.write(C.DMM["auto_range"].format(prefix=f[4]))
        elif rng in f[3]:
            self.t.write(C.DMM["set_range"].format(prefix=f[4], range=f[3][rng]))

    def dmm_read(self) -> tuple[float, str | None]:
        """Trả về (giá trị theo đơn vị gốc, khóa chức năng máy đang ở). OL -> inf."""
        return parse_dmm(self.t.query(C.DMM["measure"]))

    def dmm_measure(self) -> float:
        return self.dmm_read()[0]

    def close(self):
        try:
            self.t.write(C.PSU["local"])
        except Exception:  # noqa: BLE001
            pass
        self.t.close()
