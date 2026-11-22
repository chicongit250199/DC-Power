"""Bộ đệm dữ liệu, ghi CSV, tích lũy dung lượng, thống kê DMM."""
from __future__ import annotations

import csv
import datetime as dt
import math
from pathlib import Path

import numpy as np


class RingBuffer:
    def __init__(self, cols: int, capacity: int = 500_000):
        self._d = np.zeros((capacity, cols))
        self._n = 0
        self._cap = capacity

    def append(self, *row: float):
        if self._n == self._cap:  # dồn nửa sau lên đầu
            half = self._cap // 2
            self._d[:half] = self._d[half:]
            self._n = half
        self._d[self._n] = row
        self._n += 1

    def data(self) -> np.ndarray:
        return self._d[: self._n]

    def clear(self):
        self._n = 0

    def __len__(self):
        return self._n


class CsvLogger:
    def __init__(self, header: list[str]):
        self.header = header
        self._f = None
        self._w = None
        self.path: Path | None = None
        self.rows = 0

    @property
    def active(self) -> bool:
        return self._f is not None

    def start(self, path: Path):
        self.stop()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(path, "w", newline="", encoding="utf-8-sig")  # utf-8-sig: Excel đọc đúng
        self._w = csv.writer(self._f)
        self._w.writerow(self.header)
        self.path = path
        self.rows = 0

    def write(self, ts: float, *vals):
        if not self._w:
            return
        stamp = dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self._w.writerow([stamp, *vals])
        self.rows += 1
        if self.rows % 50 == 0:
            self._f.flush()

    def stop(self):
        if self._f:
            self._f.close()
        self._f = self._w = None


class EnergyMeter:
    """Tích phân dòng và công suất theo thời gian -> mAh, Wh."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.mah = 0.0
        self.wh = 0.0
        self.seconds = 0.0
        self._last: tuple[float, float, float] | None = None

    def add(self, t: float, v: float, a: float, running: bool):
        if self._last and running:
            dt_s = t - self._last[0]
            if 0 < dt_s < 5:  # bỏ khoảng trống khi mất kết nối
                a_avg = (a + self._last[2]) / 2
                p_avg = (v * a + self._last[1] * self._last[2]) / 2
                self.mah += a_avg * dt_s / 3.6
                self.wh += p_avg * dt_s / 3600
                self.seconds += dt_s
        self._last = (t, v, a)


class Stats:
    def __init__(self):
        self.reset()

    def reset(self):
        self.n = 0
        self.min = math.inf
        self.max = -math.inf
        self._sum = 0.0

    def add(self, x: float):
        if not math.isfinite(x):
            return
        self.n += 1
        self._sum += x
        self.min = min(self.min, x)
        self.max = max(self.max, x)

    @property
    def avg(self) -> float:
        return self._sum / self.n if self.n else math.nan


_PREFIX = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p")]


def si_format(x: float, unit: str, digits: int = 5) -> str:
    """4.7e3, 'Ω' -> '4.7000 kΩ'"""
    if x is None or not math.isfinite(x):
        return f"OL {unit}"
    if x == 0:
        return f"0.0000 {unit}"
    ax = abs(x)
    for f, p in _PREFIX:
        if ax >= f:
            break
    s = x / f
    decimals = max(0, digits - 1 - int(math.floor(math.log10(abs(s)))))
    return f"{s:.{decimals}f} {p}{unit}"


def log_dir() -> Path:
    return Path.home() / "Documents" / "DC Power Logs"
