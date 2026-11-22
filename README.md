# DC Power

Phần mềm điều khiển nguồn DC + đồng hồ vạn năng OWON SPM3103 (thay thế phần mềm gốc).

- Python 3.9+ · PySide6 (Qt) · pyqtgraph · pyserial
- Chạy trên Windows (code đa nền tảng, dev/test được trên macOS)
- Có chế độ **Giả lập (Demo)** để dùng thử khi chưa cắm máy

## Chạy thử
```
python -m venv .venv
.venv\Scripts\activate            # macOS: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```
Chọn cổng **Giả lập (Demo)** → **Kết nối** để xem thử.

## Build ra .exe (trên Windows)
Chạy `build_windows.bat` → kết quả ở `dist\DC Power\DC Power.exe`
(cả thư mục `dist\DC Power` là bản cài, copy nguyên thư mục sang máy khác).

## Logo
Thả ảnh vào `upload/` (PNG nền trong suốt / ICO / SVG). Ảnh đầu tiên tìm thấy được dùng
cho logo trên thanh công cụ, icon cửa sổ và icon .exe.

## Lệnh SCPI
Toàn bộ lệnh ở `src/dcpower/device/commands.py` — **chưa xác nhận trên máy thật**,
sai lệnh nào thì sửa tại đây.

## Cấu trúc
```
src/dcpower/
  device/   commands.py (bảng lệnh), transport.py (serial + giả lập), spm.py (driver)
  core/     worker.py (luồng giao tiếp, tự kết nối lại), data.py (buffer, CSV, mAh/Wh)
  ui/       main_window, chart_panel, psu_panels, gauge, dmm_panel, sequence_panel, style
docs/SPEC.md   đặc tả tính năng
tests/         pytest
```
Log nguồn lưu tại `Documents/DC Power Logs/`.
