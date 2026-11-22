# DC Power

Phần mềm điều khiển nguồn DC OWON SPM3103 (thay thế phần mềm gốc), chạy trên Windows.

- Ngôn ngữ: Python 3.11+
- Giao diện: PySide6 (Qt)
- Giao tiếp: SCPI qua USB/COM (pyserial)
- Đóng gói: PyInstaller -> .exe

## Chạy thử
```
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS: source .venv/bin/activate)
pip install -r requirements.txt
python -m dcpower
```

## Cấu trúc
```
src/dcpower/
  device/   # driver SCPI cho SPM3103
  core/     # logic: đo, log, sequence, cấu hình
  ui/       # giao diện PySide6
docs/       # đặc tả, tài liệu lệnh SCPI
tests/      # unit test (có máy giả lập)
assets/     # icon, ảnh
```
