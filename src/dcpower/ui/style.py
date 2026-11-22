"""Giao diện tối, panel bán trong suốt để thấy hình nền."""

COLOR_V = "#f5b700"   # vàng - điện áp
COLOR_A = "#1fb5ff"   # xanh - dòng điện
COLOR_W = "#c77dff"   # tím - công suất
COLOR_ON = "#1db954"
COLOR_OFF = "#e5484d"
COLOR_WARN = "#ff8b3d"

QSS = f"""
QMainWindow::separator {{ background: #2a2e36; width: 6px; height: 6px; }}
QMainWindow::separator:hover {{ background: #3d7bff; }}
QDockWidget {{ color: #c9ced6; font-weight: 600; }}
QDockWidget::title {{ background: rgba(30,34,41,220); padding: 6px 8px; border-bottom: 1px solid #2a2e36; }}
QWidget#Panel {{ background: rgba(24,27,33,215); }}
QLabel {{ color: #d7dbe2; }}
QLabel[role="cap"] {{ color: #8b93a1; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QLabel[role="big"] {{ font-family: "Consolas","Menlo",monospace; font-weight: 700; }}
QPushButton, QToolButton {{
    background: #2a2f38; color: #e6e9ee; border: 1px solid #3a404b;
    border-radius: 6px; padding: 6px 12px;
}}
QPushButton:hover, QToolButton:hover {{ background: #343a45; }}
QPushButton:pressed {{ background: #1f232a; }}
QPushButton:checked {{ background: #3d7bff; border-color: #3d7bff; color: white; }}
QPushButton:disabled {{ color: #6b7280; }}
QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit {{
    background: #1b1e24; color: #f0f2f5; border: 1px solid #3a404b;
    border-radius: 5px; padding: 4px 6px; selection-background-color: #3d7bff;
}}
QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{ border-color: #3d7bff; }}
QComboBox QAbstractItemView {{ background: #1b1e24; color: #f0f2f5; }}
QTableWidget {{ background: #1b1e24; color: #e6e9ee; gridline-color: #2a2e36; border: 1px solid #2a2e36; }}
QHeaderView::section {{ background: #242830; color: #aab1bd; border: none; padding: 4px; }}
QToolBar {{ background: #1b1e24; border-bottom: 1px solid #2a2e36; spacing: 6px; padding: 4px; }}
QStatusBar {{ background: #1b1e24; color: #aab1bd; }}
QMenuBar {{ background: #1b1e24; color: #d7dbe2; }}
QMenuBar::item:selected {{ background: #2a2f38; }}
QMenu {{ background: #1f232a; color: #e6e9ee; border: 1px solid #3a404b; }}
QMenu::item:selected {{ background: #3d7bff; }}
QCheckBox {{ color: #d7dbe2; }}
QGroupBox {{ color: #8b93a1; border: 1px solid #2a2e36; border-radius: 6px; margin-top: 10px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}
"""


def output_button_qss(on: bool) -> str:
    c = COLOR_ON if on else COLOR_OFF
    return (
        f"QPushButton {{ background: {c}; color: white; border: none; border-radius: 10px;"
        f" font-size: 20px; font-weight: 800; padding: 10px 18px; }}"
        f"QPushButton:hover {{ border: 2px solid white; }}"
        f"QPushButton:disabled {{ background: #3a404b; color: #8b93a1; }}"
    )
