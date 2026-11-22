"""Chạy trực tiếp: python run.py (và dùng cho PyInstaller)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from dcpower.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
