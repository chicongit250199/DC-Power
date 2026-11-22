"""Bảng lệnh SCPI cho OWON SPM3103.

Đã đối chiếu với phần mềm gốc "DC power multimeter control V1.7.6" và test trên
máy thật (OWON,SPM3103, FV:V2.1.0) qua cổng CH340, 115200 8N1.
"""

SERIAL = {
    "baudrate": 115200,
    "timeout": 0.5,          # giây, chờ phản hồi
    "terminator": "\r\n",    # lệnh ghi (giống phần mềm gốc)
    "query_terminator": "\n",  # lệnh hỏi (giống phần mềm gốc)
    "write_delay": 0.1,      # giây nghỉ sau mỗi lệnh ghi (bản gốc cũng 100 ms; <50 ms máy bỏ lệnh)
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
    # -> "V,A,W,OVP,OCP,OTP,chế độ"  vd "12.001,0.153,1.836,OFF,OFF,OFF,1"
    # chế độ: 0 = Standby, 1 = CV, 2 = CC, 3 = Lỗi (giống phần mềm gốc)
    "meas_info": "MEASure:ALL:INFO?",
    "meas_all": "MEAS:ALL?",           # -> "0.000,0.000"
    "meas_voltage": "MEAS:VOLT?",
    "meas_current": "MEAS:CURR?",
    "remote": "SYSTem:REMote",
    "local": "SYSTem:LOCal",
}

# Chức năng đồng hồ vạn năng:
# khóa -> (tên hiển thị, đơn vị, lệnh chọn chức năng, {nhãn range: giá trị SCPI}, tiền tố lệnh range)
# Range "AUTO" luôn có trên giao diện. Lệnh range: "<tiền tố>:RANGe <giá trị>" / "<tiền tố>:RANGe:AUTO 1".
DMM_FUNCTIONS = {
    "DCV":  ("DC V",       "V",  "FUNCtion:VOLTage:DC",
             {"200mV": "200E-3", "2V": "2", "20V": "20", "200V": "200", "1000V": "1000"}, "VOLT:DC"),
    "ACV":  ("AC V",       "V",  "FUNCtion:VOLTage:AC",
             {"200mV": "200E-3", "2V": "2", "20V": "20", "200V": "200", "750V": "750"}, "VOLT:AC"),
    "DCA":  ("DC A",       "A",  "FUNCtion:CURRent:DC", {"200mA": "200E-3", "10A": "10"}, "CURR:DC"),
    "ACA":  ("AC A",       "A",  "FUNCtion:CURRent:AC", {"200mA": "200E-3", "10A": "10"}, "CURR:AC"),
    "RES":  ("Điện trở",   "Ω",  "FUNCtion:RESistance",
             {"200": "200", "2k": "2E3", "20k": "20E3", "200k": "200E3", "2M": "2E6",
              "20M": "20E6", "100M": "100E6"}, "RES"),
    "CAP":  ("Tụ điện",    "F",  "FUNCtion:CAPacitance", {}, "CAP"),
    "DIOD": ("Diode",      "V",  "FUNCtion:DIODe",       {}, "DIOD"),
    "CONT": ("Thông mạch", "Ω",  "FUNCtion:CONTinuity",  {}, "CONT"),
}

DMM = {
    # -> "VOLT:DC,+0.0016V,AUTO,2V" | "RES,OL,AUTO,200k Ohm" | "DIOD,Open,Manual,"
    "measure": "CONFigure:ALL?",
    "set_range": "{prefix}:RANGe {range}",
    "auto_range": "{prefix}:RANGe:AUTO 1",
    "hold": ":MULTimeter:HOLD {state}",   # ON / OFF
    "continuity_threshold_ohm": 50.0,
}
