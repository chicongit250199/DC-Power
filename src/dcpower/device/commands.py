"""Bảng lệnh SCPI cho OWON SPM3103.

CHƯA XÁC NHẬN TRÊN MÁY THẬT. Các lệnh dựa trên quy ước SCPI chung của OWON
(dòng SP/SPE cho nguồn, dòng XDM cho đồng hồ vạn năng). Khi test với máy thật,
lệnh nào sai chỉ cần sửa ở file này.
"""

SERIAL = {
    "baudrate": 115200,
    "timeout": 0.5,          # giây, chờ phản hồi
    "terminator": "\n",
}

PSU = {
    "idn": "*IDN?",
    "set_voltage": "VOLT {value:.3f}",
    "set_current": "CURR {value:.3f}",
    "set_voltage_limit": "VOLT:LIM {value:.3f}",
    "set_current_limit": "CURR:LIM {value:.3f}",
    "get_voltage_set": "VOLT?",
    "get_current_set": "CURR?",
    "get_voltage_limit": "VOLT:LIM?",
    "get_current_limit": "CURR:LIM?",
    "output_on": "OUTP ON",
    "output_off": "OUTP OFF",
    "get_output": "OUTP?",
    # Đọc V và A trong 1 lệnh (nhanh hơn). Nếu máy không hỗ trợ sẽ tự
    # chuyển sang đọc riêng meas_voltage / meas_current.
    "meas_all": "MEAS:ALL?",
    "meas_voltage": "MEAS:VOLT?",
    "meas_current": "MEAS:CURR?",
    "remote": "SYST:REM",
    "local": "SYST:LOC",
}

# Chức năng đồng hồ vạn năng: khóa -> (tên hiển thị, đơn vị, lệnh cấu hình, danh sách range)
# Range "AUTO" luôn có. Lệnh range: DMM["set_range"].
DMM_FUNCTIONS = {
    "DCV":  ("DC V",       "V",  "CONF:VOLT:DC",  ["200mV", "2V", "20V", "200V", "1000V"]),
    "ACV":  ("AC V",       "V",  "CONF:VOLT:AC",  ["200mV", "2V", "20V", "200V", "750V"]),
    "DCA":  ("DC A",       "A",  "CONF:CURR:DC",  ["200uA", "2mA", "20mA", "200mA", "2A", "10A"]),
    "ACA":  ("AC A",       "A",  "CONF:CURR:AC",  ["20mA", "200mA", "2A", "10A"]),
    "RES":  ("Điện trở",   "Ω",  "CONF:RES",      ["200", "2k", "20k", "200k", "2M", "20M", "100M"]),
    "CAP":  ("Tụ điện",    "F",  "CONF:CAP",      ["2nF", "20nF", "200nF", "2uF", "20uF", "200uF", "10mF"]),
    "DIOD": ("Diode",      "V",  "CONF:DIOD",     []),
    "CONT": ("Thông mạch", "Ω",  "CONF:CONT",     []),
}

DMM = {
    "measure": "MEAS1?",         # đọc giá trị hiện tại
    "set_range": "RANGE {range}",
    "auto_range": "AUTO",
    "continuity_threshold_ohm": 50.0,
}
