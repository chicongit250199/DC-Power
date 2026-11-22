# Đặc tả yêu cầu - DC Power (OWON SPM3103)

Ngôn ngữ giao diện: Tiếng Việt. Chạy trên Windows (code đa nền tảng, test được trên macOS).

## Bố cục cửa sổ chính (mặc định - người dùng kéo/đổi kích thước được)
```
 Thanh trên: [Cổng COM ▾] [Kết nối]  trạng thái kết nối        [Logo]
┌───────────────────────────────┬──────────────┐
│ [ OUTPUT ON/OFF ]  CV/CC  ... │  Số V / A / W│
│                               │  (Set/Thực)  │
│   Đồ thị V & A                │  mAh / Wh    │
│   (2/3 rộng, 1/2 cao)         ├──────────────┤
│                               │  Set V, A,   │
│                               │  Vlim, Alim  │
│                               │  Preset/Timer│
├───────────────────────────────┼──────────────┤
│   Đồng hồ kim + số ở giữa     │  Chọn thang  │
│   (DMM)                       │  DCV,Diode,  │
│                               │  C, R... Log │
└───────────────────────────────┴──────────────┘
 (Panel Sequence: mở từ menu, tab cạnh panel Set)
```

## 1. Nguồn DC
- [x] Đồ thị V và A rõ ràng, cập nhật nhanh nhất máy cho phép; chiếm 1/2 cao, 2/3 rộng
- [x] Nút OUTPUT ON/OFF to, dễ bấm, nằm sát đồ thị
- [x] Số chính xác V, A (set và thực tế) cạnh đồ thị, phía trên
- [x] Ô set V, A, V limit, A limit nằm dưới phần số
- [x] Hiển thị công suất W, trạng thái CV/CC
- [x] Bảo vệ OVP/OCP: cảnh báo đổi màu + bíp, tùy chọn tự tắt output
- [x] Điều khiển đồ thị: tạm dừng, zoom/kéo, khoảng thời gian, xóa, chụp ảnh
- [x] Ghi log V/A/W ra CSV (mở bằng Excel)
- [x] Preset điện áp/dòng (bấm 1 nút; chuột phải để lưu giá trị hiện tại)
- [x] Sequence: chuỗi bước V/A/thời gian, lặp N lần
- [x] Hẹn giờ tắt output
- [x] Tích lũy dung lượng mAh / Wh, nút reset

## 2. Cửa sổ
- [x] Thay đổi kích thước cửa sổ, bố trí/đổi kích thước/tách rời các panel
- [x] Thay đổi hình nền (ảnh hoặc màu)
- [x] Logo riêng (lấy từ thư mục upload/)
- [x] Lưu cấu hình: bố cục, hình nền, cổng COM, giá trị set
- [x] Phím tắt

## 3. Đồng hồ vạn năng (1/2 dưới)
- [x] Trái: đồng hồ kim kèm số ở giữa
- [x] Phải: chọn chức năng / thang đo (DCV, ACV, DCA, ACA, Ω, C, Diode, Thông mạch, Auto/range)
- [x] Hold, Min/Max/Trung bình, Relative, thông mạch có bíp
- [x] Ghi lại giá trị đo (từng giá trị hoặc tự động), xuất CSV

## 4. Kết nối
- [x] Chọn cổng COM, nút Kết nối, chế độ Giả lập (Demo) khi không có máy
- [x] Tự kết nối lại khi rớt USB, hiển thị trạng thái

## Phím tắt
| Phím | Chức năng |
|---|---|
| F5 | Bật/tắt Output |
| F2 | Kết nối / Ngắt |
| F6 | Hold đồng hồ vạn năng |
| F7 | Ghi giá trị đồng hồ vạn năng |
| F8 | Bắt đầu/dừng ghi log nguồn |
| Space | Tạm dừng đồ thị |
| Ctrl+S | Chụp ảnh đồ thị |

## Lưu ý kỹ thuật
- Lệnh SCPI chưa được xác nhận trên máy thật -> toàn bộ nằm ở `src/dcpower/device/commands.py`.
- Tốc độ đo bị giới hạn bởi máy (ước tính 5-20 lần/giây); nguồn và DMM đọc xen kẽ.
