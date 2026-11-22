"""Preset M1-M8: 4 giá trị, chuyển đổi preset kiểu cũ, chặn V > V limit."""
from dcpower.ui.psu_panels import DEFAULT_PRESETS, N_PRESETS, normalize_presets, preset_problem


def test_defaults_are_8_valid_presets():
    assert len(DEFAULT_PRESETS) == N_PRESETS == 8
    assert all(len(p) == 4 and not preset_problem(*p) for p in DEFAULT_PRESETS)


def test_old_format_migrates_with_limits():
    old = [[20.0, 10.0], [5.0, 2.0], [9.0, 1.0], [12.0, 2.0], [24.0, 1.0], [30.0, 0.5]]
    p = normalize_presets(old)
    assert len(p) == 8
    assert p[0] == (20.0, 10.0, 21.0, 10.1)
    assert p[5] == (30.0, 0.5, 31.0, 0.6)
    assert p[6:] == DEFAULT_PRESETS[6:]          # thiếu thì lấy mặc định
    assert all(not preset_problem(*x) for x in p)


def test_new_format_kept_and_garbage_ignored():
    p = normalize_presets([[1, 2, 3, 4], "rác", None])
    assert p[0] == (1.0, 2.0, 3.0, 4.0)
    assert p[1] == DEFAULT_PRESETS[1] and p[2] == DEFAULT_PRESETS[2]
    assert normalize_presets(None) == DEFAULT_PRESETS


def test_problem_detection():
    assert preset_problem(25, 1, 6, 2)            # V > V limit
    assert preset_problem(5, 3, 6, 2)             # A > A limit
    assert preset_problem(6, 2, 6, 2) == ""       # bằng nhau thì hợp lệ
