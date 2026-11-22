"""Điểm khởi chạy: python -m dcpower"""
import os
import sys

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")


def main() -> None:
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QApplication

    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))  # số dùng dấu chấm

    from .ui.main_window import APP_NAME, MainWindow
    from .ui.style import QSS

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
