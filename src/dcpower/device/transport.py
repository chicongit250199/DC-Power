"""Kênh truyền: cổng serial thật hoặc máy giả lập."""
from __future__ import annotations

import math
import random
import re
import time

from . import commands as C

SIM_PORT = "Giả lập (Demo)"


class TransportError(Exception):
    pass


class SerialTransport:
    def __init__(self, port: str):
        import serial  # noqa: import muộn để chạy Demo không cần pyserial

        try:
            self._ser = serial.Serial(
                port,
                baudrate=C.SERIAL["baudrate"],
                timeout=C.SERIAL["timeout"],
                write_timeout=C.SERIAL["timeout"],
            )
        except Exception as e:  # noqa: BLE001
            raise TransportError(str(e)) from e
        self._term = C.SERIAL["terminator"].encode()
        self._qterm = C.SERIAL.get("query_terminator", C.SERIAL["terminator"]).encode()
        time.sleep(0.1)
        self._ser.reset_input_buffer()

    def write(self, cmd: str, term: bytes | None = None) -> None:
        try:
            self._ser.write(cmd.encode() + (self._term if term is None else term))
        except Exception as e:  # noqa: BLE001
            raise TransportError(str(e)) from e
        if term is None:
            # Máy bận sau mỗi lệnh ghi: gửi dồn thì chỉ nhận lệnh đầu, hỏi ngay thì không trả lời
            time.sleep(C.SERIAL["write_delay"])

    def query(self, cmd: str) -> str:
        try:
            self._ser.reset_input_buffer()  # bỏ dòng thừa còn sót để không lệch cặp hỏi/đáp
        except Exception:  # noqa: BLE001
            pass
        self.write(cmd, self._qterm)
        try:
            line = self._ser.readline()
        except Exception as e:  # noqa: BLE001
            raise TransportError(str(e)) from e
        if not line:
            raise TransportError(f"Không có phản hồi cho '{cmd}'")
        return line.decode(errors="replace").strip()

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:  # noqa: BLE001
            pass


def list_ports() -> list[str]:
    try:
        from serial.tools import list_ports as lp

        ports = [p.device for p in lp.comports()]
    except Exception:  # noqa: BLE001
        ports = []
    return ports + [SIM_PORT]


class SimTransport:
    """Máy SPM3103 giả lập: tải trở 10Ω, có giới hạn dòng (CC), DMM ra số ngẫu nhiên."""

    LOAD_OHM = 10.0

    def __init__(self):
        self.vset, self.iset = 5.0, 1.0
        self.vlim, self.ilim = 31.0, 10.5
        self.out = False
        self.func = "DCV"
        self._t0 = time.monotonic()

    def _psu(self) -> tuple[float, float]:
        if not self.out:
            return 0.0, 0.0
        t = time.monotonic() - self._t0
        load = self.LOAD_OHM * (1 + 0.15 * math.sin(t * 0.7))
        i = self.vset / load
        v = self.vset
        if i > self.iset:  # chế độ CC
            i = self.iset
            v = i * load
        noise = lambda x: x * (1 + random.gauss(0, 0.0008))  # noqa: E731
        return noise(v), noise(i)

    def _dmm(self) -> float:
        t = time.monotonic() - self._t0
        base = {
            "DCV": 3.3 + 0.4 * math.sin(t),
            "ACV": 230 + 2 * math.sin(t * 0.3),
            "DCA": 0.120 + 0.01 * math.sin(t),
            "ACA": 0.5,
            "RES": 4700.0,
            "CAP": 1e-6,
            "DIOD": 0.62,
            "CONT": 0.8 if int(t / 3) % 2 else 1e9,
        }[self.func]
        return base * (1 + random.gauss(0, 0.001))

    def write(self, cmd: str) -> None:
        self._handle(cmd)

    def query(self, cmd: str) -> str:
        time.sleep(0.01)  # mô phỏng độ trễ USB
        r = self._handle(cmd)
        if r is None:
            raise TransportError(f"Không có phản hồi cho '{cmd}'")
        return r

    def _handle(self, cmd: str) -> str | None:
        c = cmd.strip().upper()
        num = re.search(r"[-+]?\d*\.?\d+(?:E[-+]?\d+)?", c)
        val = float(num.group()) if num else 0.0
        if c == "*IDN?":
            return "OWON,SPM3103,SIM0001,V1.0 (GIA LAP)"
        if c == "MEASURE:ALL:INFO?":
            v, i = self._psu()
            mode = 0 if not self.out else (2 if i >= self.iset * 0.999 else 1)
            return f"{v:.3f},{i:.3f},{v * i:.3f},OFF,OFF,OFF,{mode}"
        if c == "MEAS:ALL?":
            v, i = self._psu()
            return f"{v:.3f},{i:.3f}"
        if c == "MEAS:VOLT?":
            return f"{self._psu()[0]:.3f}"
        if c == "MEAS:CURR?":
            return f"{self._psu()[1]:.3f}"
        if c == "VOLT?":
            return f"{self.vset:.3f}"
        if c == "CURR?":
            return f"{self.iset:.3f}"
        if c == "VOLT:LIM?":
            return f"{self.vlim:.3f}"
        if c == "CURR:LIM?":
            return f"{self.ilim:.3f}"
        if c == "OUTP?":
            return "ON" if self.out else "OFF"
        if c.startswith("VOLT:LIM "):
            self.vlim = val
        elif c.startswith("CURR:LIM "):
            self.ilim = val
        elif c.startswith("VOLT "):
            self.vset = val
        elif c.startswith("CURR "):
            self.iset = val
        elif c == "OUTP ON":
            self.out = True
        elif c == "OUTP OFF":
            self.out = False
        elif c.startswith("FUNC") and not c.endswith("?"):
            for k, f in C.DMM_FUNCTIONS.items():
                if c == f[2].upper():
                    self.func = k
        elif c == "FUNCTION?" or c == "FUNC?":
            return C.DMM_FUNCTIONS[self.func][4]
        elif c == "CONFIGURE:ALL?" or c == "CONF:ALL?":
            f = C.DMM_FUNCTIONS[self.func]
            val = self._dmm()
            unit = {"Ω": " Ohm"}.get(f[1], f[1])
            txt = "OL" if val > 1e8 else f"{val:+.4f}{unit}"
            return f"{f[4]},{txt},AUTO,"
        elif c in ("MEAS1?", "MEAS?"):
            return "ERR"
        return None

    def close(self) -> None:
        pass


def open_transport(port: str):
    if port == SIM_PORT:
        return SimTransport()
    return SerialTransport(port)
