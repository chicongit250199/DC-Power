"""Phân tích phản hồi thật của OWON SPM3103 (FV:V2.1.0)."""
import math

import pytest

from dcpower.device.spm import parse_dmm
from dcpower.device.transport import TransportError


@pytest.mark.parametrize("text,value,key", [
    ("VOLT:DC,+0.0016V,AUTO,2V", 0.0016, "DCV"),
    ("VOLT:DC,+000.18mV,Manual,200mV", 0.00018, "DCV"),
    ("VOLT:AC,+0.4670V,AUTO,2V", 0.467, "ACV"),
    ("CURR:DC,+00.000A,Manual,10A", 0.0, "DCA"),
    ("CAP,+12.345nF,AUTO,20nF", 12.345e-9, "CAP"),
    ("RES,+1.234k Ohm,AUTO,2k Ohm", 1234.0, "RES"),
    ("RES,+5.00M Ohm,AUTO,20M Ohm", 5e6, "RES"),
])
def test_parse_dmm_values(text, value, key):
    v, k = parse_dmm(text)
    assert v == pytest.approx(value)
    assert k == key


@pytest.mark.parametrize("text,key", [
    ("RES,OL,AUTO,200k Ohm", "RES"),
    ("CONT,OL,Manual,", "CONT"),
    ("DIOD,Open,Manual,", "DIOD"),
])
def test_parse_dmm_overload(text, key):
    v, k = parse_dmm(text)
    assert math.isinf(v) and k == key


def test_parse_dmm_error():
    with pytest.raises(TransportError):
        parse_dmm("ERR")
