"""Chuẩn bị tài nguyên cho bản build .exe.

- Tạo icon .ico nhiều cỡ (16..256 px) từ ảnh đầu tiên trong upload/.
- Thu nhỏ logo (ảnh gốc có thể rất lớn, vd 7558x5669) để exe khởi động nhanh, nhẹ.

Kết quả: build/assets/app.ico và build/assets/upload/<logo>.png
Dùng: python tools/make_icon.py
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "upload"
OUT = ROOT / "build" / "assets"
EXT = (".png", ".jpg", ".jpeg", ".bmp", ".ico")
LOGO_MAX = 1600


def main() -> None:
    logos = sorted(p for p in SRC.iterdir() if p.suffix.lower() in EXT) if SRC.is_dir() else []
    (OUT / "upload").mkdir(parents=True, exist_ok=True)
    if not logos:
        print("Không có logo trong upload/ -> build không có icon riêng")
        return
    src = logos[0]
    img = Image.open(src).convert("RGBA")
    print(f"Logo: {src.name} {img.width}x{img.height}")

    # Logo thu nhỏ đóng gói kèm exe
    small = img.copy()
    small.thumbnail((LOGO_MAX, LOGO_MAX), Image.LANCZOS)
    small.save(OUT / "upload" / (src.stem + ".png"), optimize=True)

    # Icon: khung vuông trong suốt, logo căn giữa
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    square.resize((256, 256), Image.LANCZOS).save(OUT / "app.ico", sizes=sizes)
    print(f"Đã tạo {OUT / 'app.ico'} và {OUT / 'upload' / (src.stem + '.png')} ({small.width}x{small.height})")


if __name__ == "__main__":
    main()
