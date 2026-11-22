"""Driver OWON SPM3103 dựa trên bảng lệnh commands.py."""
from __future__ import annotations

import re

from . import commands as C
from .transport import TransportError, open_transport

_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def parse_floats(text: str) -> list[float]:
    return [float(x) for x in _NUM.findall(text)]


class SPM3103:
    def __init__(self, port: str):
        self.t = open_transport(port)
        self._meas_all_ok = True
        self.idn = self.t.query(C.PSU["idn"])
        try:
            self.t.write(C.PSU["remote"])
        except TransportError:
            pass

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
        self.t.write(C.DMM_FUNCTIONS[key][2])

    def dmm_range(self, rng: str):
        if rng == "AUTO":
            self.t.write(C.DMM["auto_range"])
        else:
            self.t.write(C.DMM["set_range"].format(range=rng))

    def dmm_measure(self) -> float:
        vals = parse_floats(self.t.query(C.DMM["measure"]))
        if not vals:
            raise TransportError("Phản hồi DMM lạ")
        return vals[0]

    def close(self):
        try:
            self.t.write(C.PSU["local"])
        except Exception:  # noqa: BLE001
            pass
        self.t.close()
