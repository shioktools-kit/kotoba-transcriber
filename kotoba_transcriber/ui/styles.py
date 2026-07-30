"""配色とスタイルシート。色の定義はこのファイルだけに置く。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"

THEME_LABELS: tuple[tuple[str, str], ...] = (
    ("システムに追従", THEME_SYSTEM),
    ("ライト", THEME_LIGHT),
    ("ダーク", THEME_DARK),
)


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_soft: str
    accent_disabled: str
    danger: str
    success: str


LIGHT = Palette(
    background="#F5F6F8",
    surface="#FFFFFF",
    surface_alt="#F0F1F4",
    border="#D8DBE0",
    text="#1F2328",
    text_muted="#6B7280",
    accent="#2563EB",
    accent_hover="#1D4ED8",
    accent_soft="#EFF4FF",
    accent_disabled="#A9BCE8",
    danger="#B91C1C",
    success="#15803D",
)

DARK = Palette(
    background="#1B1D21",
    surface="#25282D",
    surface_alt="#2E3238",
    border="#3B4048",
    text="#E4E6EA",
    text_muted="#9AA1AB",
    accent="#5A8DEF",
    accent_hover="#7AA5F5",
    accent_soft="#2A3548",
    accent_disabled="#3D4A63",
    danger="#F87171",
    success="#4ADE80",
)


def palette_for(theme: str, system_is_dark: bool = False) -> Palette:
    if theme == THEME_DARK:
        return DARK
    if theme == THEME_LIGHT:
        return LIGHT
    return DARK if system_is_dark else LIGHT


def qt_palette(p: Palette) -> QPalette:
    """QPalette も揃える。

    チェックボックスのチェックやコンボボックスの矢印は Qt(Fusion) が
    QPalette を見て描くので、スタイルシートだけ暗くすると描画が壊れる。
    """
    palette = QPalette()
    window = QColor(p.background)
    surface = QColor(p.surface)
    field = QColor(p.surface_alt)
    text = QColor(p.text)
    muted = QColor(p.text_muted)
    accent = QColor(p.accent)

    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, field)
    palette.setColor(QPalette.AlternateBase, surface)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.PlaceholderText, muted)
    palette.setColor(QPalette.Button, surface)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.Highlight, accent)
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipBase, surface)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Link, accent)

    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, muted)

    return palette


def stylesheet(p: Palette) -> str:
    return f"""
/* 背景色は QWidget 全体には指定しない。指定するとチェックボックスや
   コンボボックスが QSS 描画に切り替わり、枠や矢印が消えてしまうため、
   ウィンドウなど「面」になる widget だけに当てる。 */
QWidget {{
    color: {p.text};
    font-family: "Yu Gothic UI", "Meiryo UI", sans-serif;
    font-size: 13px;
}}
QMainWindow, QMainWindow > QWidget, QDialog {{ background-color: {p.background}; }}

QLabel#hint {{ color: {p.text_muted}; }}

QGroupBox {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 6px;
    margin-top: 10px;
    padding: 12px 12px 10px 12px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {p.text_muted};
}}

QPushButton {{
    background-color: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: 5px;
    padding: 6px 14px;
    min-height: 18px;
}}
QPushButton:hover {{ background-color: {p.accent_soft}; border-color: {p.accent}; }}
QPushButton:disabled {{ color: {p.text_muted}; background-color: {p.background}; border-color: {p.border}; }}

QPushButton#primary {{
    background-color: {p.accent};
    border: 1px solid {p.accent};
    color: #FFFFFF;
    font-weight: bold;
    padding: 8px 22px;
}}
QPushButton#primary:hover {{ background-color: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton#primary:disabled {{ background-color: {p.accent_disabled}; border-color: {p.accent_disabled}; color: {p.surface}; }}

QLineEdit, QPlainTextEdit, QTableWidget, QComboBox, QSpinBox {{
    background-color: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: 5px;
    selection-background-color: {p.accent_soft};
    selection-color: {p.text};
}}
QLineEdit, QComboBox, QSpinBox {{ padding: 5px 8px; }}
QLineEdit:read-only {{ color: {p.text_muted}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {p.text_muted}; }}

QComboBox QAbstractItemView {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    selection-background-color: {p.accent_soft};
    selection-color: {p.text};
    outline: none;
}}

QPlainTextEdit#log {{
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    color: {p.text_muted};
    padding: 6px;
}}

QTableWidget {{ gridline-color: {p.border}; }}
QTableWidget::item {{ padding: 4px 6px; }}
QTableWidget::item:selected {{ background-color: {p.accent_soft}; color: {p.text}; }}
QHeaderView::section {{
    background-color: {p.background};
    border: none;
    border-bottom: 1px solid {p.border};
    padding: 6px;
    color: {p.text_muted};
    font-weight: bold;
}}

QProgressBar {{
    background-color: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: 5px;
    height: 16px;
    text-align: center;
    color: {p.text_muted};
}}
QProgressBar::chunk {{ background-color: {p.accent}; border-radius: 4px; }}

QCheckBox {{ spacing: 6px; }}
QCheckBox:disabled {{ color: {p.text_muted}; }}
QStatusBar {{ background-color: {p.surface}; border-top: 1px solid {p.border}; color: {p.text_muted}; }}
QSplitter::handle {{ background-color: transparent; height: 8px; }}

QScrollBar:vertical {{ background: {p.background}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {p.background}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QToolTip {{
    background-color: {p.surface};
    color: {p.text};
    border: 1px solid {p.border};
    padding: 4px;
}}
"""


def drop_area_qss(p: Palette, active: bool) -> str:
    """ドロップ領域のスタイル。`active` はドラッグ中の見た目。"""
    background = p.accent_soft if active else p.surface
    border = p.accent if active else p.border
    label = p.accent if active else p.text_muted
    title = p.accent if active else p.text
    return f"""
QFrame#dropArea {{
    background-color: {background};
    border: 2px dashed {border};
    border-radius: 8px;
}}
QFrame#dropArea QLabel {{ background: transparent; color: {label}; }}
QFrame#dropArea QLabel#dropTitle {{ color: {title}; font-size: 15px; font-weight: bold; }}
"""
