import math

from dcpower.core.data import EnergyMeter, RingBuffer, Stats, si_format
from dcpower.device.spm import SPM3103, parse_floats
from dcpower.device.transport import SIM_PORT
from dcpower.ui.gauge import nice_ceil


def test_si_format():
    assert si_format(4700, "Ω") == "4.7000 kΩ"
    assert si_format(0.0123, "A") == "12.300 mA"
    assert si_format(math.inf, "V") == "OL V"


def test_parse_floats():
    assert parse_floats("12.345,0.678") == [12.345, 0.678]
    assert parse_floats("1.234E+03") == [1234.0]


def test_nice_ceil():
    assert nice_ceil(3.3) == 5
    assert nice_ceil(0.12) == 0.2
    assert nice_ceil(230) == 250


def test_energy_meter():
    e = EnergyMeter()
    e.add(0, 10, 1, True)
    e.add(3600, 10, 1, True)  # bị bỏ vì khoảng trống > 5s
    assert e.mah == 0
    for t in range(1, 3601):
        e.add(3600 + t, 10, 1, True)
    assert abs(e.mah - 1000) < 1e-6 and abs(e.wh - 10) < 1e-6


def test_ring_buffer_wraps():
    b = RingBuffer(2, capacity=10)
    for i in range(25):
        b.append(i, i)
    assert b.data()[-1, 0] == 24 and len(b) <= 10


def test_stats():
    s = Stats()
    for x in (1, 2, 3):
        s.add(x)
    assert (s.min, s.max, s.avg) == (1, 3, 2)


def test_simulated_device_cc_mode():
    d = SPM3103(SIM_PORT)
    assert "SPM3103" in d.idn
    d.set_voltage(12)
    d.set_current(0.5)
    d.set_output(True)
    v, a = d.measure()
    assert d.get_output() and abs(a - 0.5) < 0.01 and v < 12  # giới hạn dòng -> CC
    d.dmm_function("RES")
    assert d.dmm_measure() > 1000
    d.close()
