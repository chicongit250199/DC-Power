"""Điểm khởi chạy: python -m dcpower"""
import os
import sys

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")


def main() -> None:
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QApplication

    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))  # số dùng dấu chấm

    from .ui.main_window import APP_NAME, MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    win = MainWindow()  # tự nạp chế độ Sáng/Tối đã lưu và đặt stylesheet
    win.show()
    if "--selftest" in sys.argv:  # kiểm tra bản build: DC Power.exe --selftest <cổng> <file kết quả>
        _selftest(app, win, *sys.argv[sys.argv.index("--selftest") + 1:][:2])
    sys.exit(app.exec())


def _selftest(app, win, port: str, out_path: str) -> None:
    """Kết nối cổng, CHỈ ĐỌC trong 6 giây (không đặt V/A, không bật output), ghi kết quả JSON rồi thoát."""
    import json
    import time

    from PySide6.QtCore import QTimer

    res = {"port": port, "psu": 0, "dmm": 0, "idn": "", "status": [], "logo": False}
    win.worker.psu_sample.connect(lambda *a: res.__setitem__("psu", res["psu"] + 1))
    win.worker.dmm_sample.connect(lambda *a: res.__setitem__("dmm", res["dmm"] + 1))
    win.worker.connected.connect(lambda idn, sp, out: res.update(idn=idn, setpoints=sp, output=out))
    win.worker.status.connect(lambda t, lvl: res["status"].append(f"{lvl}: {t}"))
    win.cmb_port.setCurrentText(port)
    win.btn_conn.click()
    t0 = time.monotonic()

    def finish():
        res["seconds"] = round(time.monotonic() - t0, 1)
        res["logo"] = win.lbl_logo.pixmap() is not None and not win.lbl_logo.pixmap().isNull()
        res["window"] = [win.width(), win.height()]
        win.btn_conn.click()
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        QTimer.singleShot(800, app.quit)

    QTimer.singleShot(6000, finish)


if __name__ == "__main__":
    main()
