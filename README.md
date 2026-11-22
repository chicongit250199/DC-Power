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
(cả thư mục `dist\DC Power` là bản cài, copy **nguyên thư mục** sang máy khác — chỉ file .exe thì không chạy).
Script tự tạo icon, bỏ phần Qt không dùng (~115 MB) và tự kiểm tra bằng máy giả lập.

Kiểm tra nhanh bản build với máy thật (chỉ đọc, không đặt thông số / bật output):
`"DC Power.exe" --selftest COM6 ketqua.json`

## Tính năng chính
- Đồ thị V/A chung 1 khung (trục V trái, trục A phải), thống kê dòng min/max/TB/dao động theo mA
- Đo nguồn ~45–50 mẫu/s (máy trả độ phân giải 1 mA), trạng thái CV/CC/OVP/OCP/OTP lấy từ máy
- 8 preset M1–M8, mỗi preset có V, A, V limit, A limit (chặn V > V limit)
- Đồng hồ vạn năng 8 chức năng, thang đo, HOLD/REL, ghi giá trị + xuất CSV
- Chế độ Sáng / Tối (Ctrl+T), bố cục kéo thả, tự giữ tỉ lệ khi đổi kích thước cửa sổ
- Phím tắt: F2 kết nối · F5 output · Ctrl+1 DC V · Ctrl+2 điện trở · Ctrl+3 diode (xem menu Trợ giúp)

## Logo
Thả ảnh vào `upload/` (PNG nền trong suốt / ICO / SVG). Ảnh đầu tiên tìm thấy được dùng
cho logo trên thanh công cụ, logo chìm, icon cửa sổ và icon .exe.

## Lệnh SCPI
Toàn bộ lệnh ở `src/dcpower/device/commands.py`, đã đối chiếu với phần mềm gốc
"DC power multimeter control V1.7.6" và test trên máy thật (SPM3103, FV:V2.1.0, CH340, 115200 8N1).
Lưu ý của máy: sau mỗi lệnh ghi phải nghỉ ≥50 ms (app dùng 100 ms), sau `SYSTem:REMote` máy bận ~0.5 s,
và máy vẫn nhận Set V cao hơn V limit (app tự chặn ở preset).

## Cấu trúc
```
src/dcpower/
  device/   commands.py (bảng lệnh), transport.py (serial + giả lập), spm.py (driver)
  core/     worker.py (luồng giao tiếp, tự kết nối lại), data.py (buffer, CSV, mAh/Wh)
  ui/       main_window, chart_panel, psu_panels, gauge, dmm_panel, sequence_panel, style
docs/SPEC.md   đặc tả tính năng
tests/         pytest
tools/         make_icon.py (icon + logo thu nhỏ cho bản build)
```
