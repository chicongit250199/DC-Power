"""Bảng màu Sáng / Tối và stylesheet. Panel bán trong suốt để thấy hình nền.

Mọi widget lấy màu từ dict T (cập nhật tại chỗ khi đổi chế độ), nên đổi chế độ không cần
khởi động lại. Màu V/A/W ở chế độ Sáng dùng tông đậm hơn để đủ tương phản trên nền trắng.
"""

PALETTES = {
    "dark": {
        "bg": "#14161a", "panel": "rgba(24,27,33,215)", "title": "rgba(30,34,41,220)",
        "text": "#d7dbe2", "strong": "#f0f2f5", "dim": "#8b93a1", "muted": "#aab1bd",
        "border": "#3a404b", "line": "#2a2e36", "bar": "#1b1e24",
        "btn": "#2a2f38", "btn_hover": "#343a45", "btn_pressed": "#1f232a", "btn_text": "#e6e9ee",
        "input": "#1b1e24", "disabled": "#6b7280",
        "accent": "#3d7bff", "accent_hover": "#5a8fff", "accent_text": "#ffffff",
        "v": "#f5b700", "a": "#1fb5ff", "w": "#c77dff",
        "on": "#1db954", "off": "#e5484d", "warn": "#ff8b3d", "flag": "#ffb547",
        "chart_bg": (14, 16, 20, 235), "chart_fg": "#aab1bd", "grid_alpha": 0.18,
        "gauge_face": (16, 18, 22, 230), "gauge_track": "#2a2e36", "gauge_ok": "#3dd6a3",
        "tick_major": "#c9ced6", "tick_minor": "#5a616d", "needle": "#ff5d5d", "hub": "#d7dbe2",
        "badge_idle": "#3a404b", "sel_row": "#3d7bff",
    },
    "light": {
        "bg": "#e9edf2", "panel": "rgba(255,255,255,235)", "title": "rgba(226,231,238,245)",
        "text": "#1f2933", "strong": "#0b1220", "dim": "#5f6b7a", "muted": "#4a5563",
        "border": "#c3cad4", "line": "#d5dbe3", "bar": "#f7f9fb",
        "btn": "#ffffff", "btn_hover": "#e8eef7", "btn_pressed": "#d6dfeb", "btn_text": "#1f2933",
        "input": "#ffffff", "disabled": "#9aa5b1",
        "accent": "#2563eb", "accent_hover": "#3b74f0", "accent_text": "#ffffff",
        "v": "#b45309", "a": "#0369a1", "w": "#7e22ce",
        "on": "#15803d", "off": "#dc2626", "warn": "#c2410c", "flag": "#b45309",
        "chart_bg": (255, 255, 255, 240), "chart_fg": "#4a5563", "grid_alpha": 0.30,
        "gauge_face": (248, 250, 252, 240), "gauge_track": "#d5dbe3", "gauge_ok": "#059669",
        "tick_major": "#334155", "tick_minor": "#94a3b8", "needle": "#dc2626", "hub": "#334155",
        "badge_idle": "#94a3b8", "sel_row": "#bfd3fb",
    },
}

THEME_NAMES = {"dark": "Tối", "light": "Sáng"}

T: dict = dict(PALETTES["dark"])  # bảng màu đang dùng (sửa tại chỗ)
CURRENT = ["dark"]


def set_theme(name: str) -> str:
    """Đổi bảng màu, trả về stylesheet mới."""
    if name not in PALETTES:
        name = "dark"
    CURRENT[0] = name
    T.clear()
    T.update(PALETTES[name])
    return build_qss()


def theme_name() -> str:
    return CURRENT[0]


def build_qss() -> str:
    t = T
    return f"""
QMainWindow::separator {{ background: {t['line']}; width: 6px; height: 6px; }}
QMainWindow::separator:hover {{ background: {t['accent']}; }}
QDockWidget {{ color: {t['text']}; font-weight: 600; }}
QDockWidget::title {{ background: {t['title']}; padding: 6px 8px; border-bottom: 1px solid {t['line']}; }}
QWidget#Panel {{ background: {t['panel']}; }}
QLabel {{ color: {t['text']}; }}
QLabel[role="cap"] {{ color: {t['dim']}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QLabel[role="dim"] {{ color: {t['dim']}; font-size: 13px; }}
QLabel[role="mono"] {{ color: {t['text']}; font-family: Consolas, Menlo, monospace; font-size: 14px; }}
QLabel[role="flag"] {{ color: {t['flag']}; font-weight: 800; font-size: 14px; }}
QLabel[role="alarm"] {{ color: {t['warn']}; font-weight: 700; font-size: 14px; }}
QLabel[role="istat"] {{ color: {t['a']}; font-family: Consolas, Menlo, monospace; font-size: 13px; padding: 2px 4px; }}
QPushButton, QToolButton {{
    background: {t['btn']}; color: {t['btn_text']}; border: 1px solid {t['border']};
    border-radius: 6px; padding: 6px 12px;
}}
QPushButton:hover, QToolButton:hover {{ background: {t['btn_hover']}; }}
QPushButton:pressed {{ background: {t['btn_pressed']}; }}
QPushButton:checked {{ background: {t['accent']}; border-color: {t['accent']}; color: {t['accent_text']}; font-weight: 700; }}
QPushButton:checked:hover {{ background: {t['accent_hover']}; }}
QPushButton:disabled {{ color: {t['disabled']}; }}
QPushButton#Primary {{ background: {t['accent']}; border-color: {t['accent']}; color: {t['accent_text']}; font-weight: 700; }}
QPushButton#Primary:hover {{ background: {t['accent_hover']}; }}
QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit, QTimeEdit {{
    background: {t['input']}; color: {t['strong']}; border: 1px solid {t['border']};
    border-radius: 5px; padding: 4px 6px; selection-background-color: {t['accent']};
    selection-color: {t['accent_text']};
}}
QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QTimeEdit:focus {{ border-color: {t['accent']}; }}
QComboBox QAbstractItemView {{ background: {t['input']}; color: {t['strong']};
    selection-background-color: {t['accent']}; selection-color: {t['accent_text']}; }}
QTableWidget {{ background: {t['input']}; color: {t['text']}; gridline-color: {t['line']};
    border: 1px solid {t['line']}; selection-background-color: {t['accent']}; selection-color: {t['accent_text']}; }}
QHeaderView {{ background: {t['input']}; }}
QHeaderView::section {{ background: {t['title']}; color: {t['muted']}; border: none; padding: 4px; }}
QTableCornerButton::section {{ background: {t['title']}; border: none; }}
QTabBar::tab {{ background: {t['bar']}; color: {t['dim']}; border: 1px solid {t['line']}; padding: 6px 14px; }}
QTabBar::tab:selected {{ background: {t['btn']}; color: {t['strong']}; border-bottom: 2px solid {t['accent']}; }}
QToolBar {{ background: {t['bar']}; border-bottom: 1px solid {t['line']}; spacing: 6px; padding: 4px; }}
QStatusBar {{ background: {t['bar']}; color: {t['muted']}; }}
QMenuBar {{ background: {t['bar']}; color: {t['text']}; }}
QMenuBar::item:selected {{ background: {t['btn_hover']}; }}
QMenu {{ background: {t['bar']}; color: {t['text']}; border: 1px solid {t['border']}; }}
QMenu::item:selected {{ background: {t['accent']}; color: {t['accent_text']}; }}
QCheckBox {{ color: {t['text']}; spacing: 6px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 3px;
    border: 1px solid {t['border']}; background: {t['input']}; }}
QCheckBox::indicator:hover {{ border-color: {t['accent']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']};
    image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png); }}
QGroupBox {{ color: {t['dim']}; border: 1px solid {t['line']}; border-radius: 6px; margin-top: 10px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: transparent; width: 10px; height: 10px; }}
QScrollBar::handle {{ background: {t['border']}; border-radius: 4px; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QToolTip {{ background: {t['bar']}; color: {t['text']}; border: 1px solid {t['border']}; }}
"""


QSS = build_qss()  # giữ tương thích: stylesheet chế độ Tối


def output_button_qss(on: bool) -> str:
    c = T["on"] if on else T["off"]
    return (
        f"QPushButton {{ background: {c}; color: white; border: none; border-radius: 10px;"
        f" font-size: 20px; font-weight: 800; padding: 10px 18px; }}"
        f"QPushButton:hover {{ border: 2px solid {T['strong']}; }}"
        f"QPushButton:disabled {{ background: {T['badge_idle']}; color: {T['bar']}; }}"
    )
