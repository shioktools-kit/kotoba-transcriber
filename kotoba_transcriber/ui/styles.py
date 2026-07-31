"""配色・タイポグラフィ・QSS。デザイントークンの定義はこのファイルだけに置く。

トークン名は `design_handoff_transcriber_redesign` の JS 実装
（`Component.palette()`）にある key と 1:1 対応させてある。突き合わせるときは
そちらの `canvasBg` / `bgTop` / ... を snake_case にしたものだと思えばよい。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtGui import QColor, QFont, QPalette

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "system"

THEME_LABELS: tuple[tuple[str, str], ...] = (
    ("システム", THEME_SYSTEM),
    ("ライト", THEME_LIGHT),
    ("ダーク", THEME_DARK),
)

# デザインの Inter / JetBrains Mono はこの環境に同梱されていないので、
# 未インストールでも近い見た目になるフォールバック列で指定する。
UI_FONT_FAMILIES: tuple[str, ...] = (
    "Inter", "Segoe UI", "Yu Gothic UI", "Meiryo UI", "sans-serif",
)
MONO_FONT_FAMILIES: tuple[str, ...] = (
    "JetBrains Mono", "Cascadia Mono", "Consolas", "monospace",
)


@dataclass(frozen=True)
class Palette:
    canvas_bg: str
    bg_top: str
    bg_bottom: str

    panel: str
    panel_deep: str
    panel_inset: str
    panel_soft: str

    border: str
    border_soft: str
    border_dashed: str

    text_pri: str
    text_body: str
    text_sec: str
    text_muted: str
    text_faint: str
    text_disabled: str

    accent: str
    accent_hover: str
    accent_soft: str
    accent_deep: str
    accent_grad_top: str
    accent_grad_bottom: str

    danger: str
    danger_soft: str
    danger_text: str

    success: str
    success_soft: str
    success_text: str

    chip_on_bg: str
    chip_on_border: str
    chip_on_text: str
    chip_off_bg: str
    chip_off_border: str
    chip_off_text: str

    seg_track_bg: str
    seg_selected_bg: str
    seg_selected_text: str
    seg_text: str

    shadow_color: str
    shadow_blur: int
    shadow_y: int


LIGHT = Palette(
    canvas_bg="#E7E9EE",
    bg_top="#F7F8FA",
    bg_bottom="#EEF0F4",
    panel="#FFFFFF",
    panel_deep="#F4F5F8",
    panel_inset="#EFF1F5",
    panel_soft="#E8EAEF",
    border="rgba(20,25,35,0.12)",
    border_soft="rgba(20,25,35,0.08)",
    border_dashed="rgba(20,25,35,0.20)",
    text_pri="#171A21",
    text_body="#262A33",
    text_sec="#5B6270",
    text_muted="#767D8A",
    text_faint="#98A0AC",
    text_disabled="#A9AFB9",
    accent="#2B58B1",
    accent_hover="#23478F",
    accent_soft="rgba(43,88,177,0.10)",
    accent_deep="#1F3E80",
    accent_grad_top="#3B6AC5",
    accent_grad_bottom="#2B51AA",
    danger="#B91C1C",
    danger_soft="rgba(185,28,28,0.08)",
    danger_text="#B91C1C",
    success="#15803D",
    success_soft="rgba(21,128,61,0.08)",
    success_text="#15803D",
    chip_on_bg="rgba(43,88,177,0.10)",
    chip_on_border="#2B58B1",
    chip_on_text="#1F3E80",
    chip_off_bg="#F4F5F8",
    chip_off_border="rgba(20,25,35,0.08)",
    chip_off_text="#767D8A",
    seg_track_bg="#EEF0F4",
    seg_selected_bg="#FFFFFF",
    seg_selected_text="#171A21",
    seg_text="#767D8A",
    shadow_color="rgba(20,30,50,0.14)",
    shadow_blur=70,
    shadow_y=30,
)

DARK = Palette(
    canvas_bg="#05060a",
    bg_top="#0A0C12",
    bg_bottom="#070810",
    panel="#0F131B",
    panel_deep="#0B0E15",
    panel_inset="#0D1118",
    panel_soft="#171B24",
    border="rgba(255,255,255,0.10)",
    border_soft="rgba(255,255,255,0.08)",
    border_dashed="rgba(255,255,255,0.16)",
    text_pri="#EEF1F6",
    text_body="#E4E8EF",
    text_sec="#9AA3B2",
    text_muted="#8B93A3",
    text_faint="#727B8B",
    text_disabled="#6A7283",
    accent="#5987DD",
    accent_hover="#6F9AE6",
    accent_soft="rgba(89,135,221,0.16)",
    accent_deep="#2B58B1",
    accent_grad_top="#3B6AC5",
    accent_grad_bottom="#2B51AA",
    danger="#F87171",
    danger_soft="rgba(248,113,113,0.14)",
    danger_text="#F8A5A5",
    success="#4ADE80",
    success_soft="rgba(74,222,128,0.14)",
    success_text="#7EE8A6",
    chip_on_bg="rgba(89,135,221,0.16)",
    chip_on_border="#5987DD",
    chip_on_text="#BFD2F2",
    chip_off_bg="#0D1118",
    chip_off_border="rgba(255,255,255,0.08)",
    chip_off_text="#8B93A3",
    seg_track_bg="#0B0E15",
    seg_selected_bg="#1C2430",
    seg_selected_text="#E9ECF2",
    seg_text="#8B93A3",
    shadow_color="rgba(0,0,0,0.55)",
    shadow_blur=70,
    shadow_y=30,
)


def palette_for(theme: str, system_is_dark: bool = False) -> Palette:
    if theme == THEME_DARK:
        return DARK
    if theme == THEME_LIGHT:
        return LIGHT
    return DARK if system_is_dark else LIGHT


_RGBA_RE = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)")


@lru_cache(maxsize=None)
def qcolor(css: str) -> QColor:
    """`#RRGGBB` / `rgba(r,g,b,a)` の CSS 色文字列を QColor にする。

    QPainter で直接描く自作ウィジェット（トグルスイッチ等）のためのもの。
    QSS 文字列に埋め込む分には CSS の書式のまま渡してよい。
    """
    match = _RGBA_RE.match(css.strip())
    if match:
        r, g, b, a = match.groups()
        alpha = float(a) if a is not None else 1.0
        return QColor(int(float(r)), int(float(g)), int(float(b)), int(round(alpha * 255)))
    return QColor(css)


def configure_app_fonts() -> None:
    """アプリ既定のフォントを設定する。呼び出しは QApplication 作成直後に一度でよい。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    font = QFont()
    font.setFamilies(list(UI_FONT_FAMILIES))
    font.setPixelSize(13)
    app.setFont(font)


def mono_font(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setFamilies(list(MONO_FONT_FAMILIES))
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def ui_font(
    pixel_size: int,
    weight: QFont.Weight = QFont.Weight.Normal,
    letter_spacing: float | None = None,
) -> QFont:
    font = QFont()
    font.setFamilies(list(UI_FONT_FAMILIES))
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    if letter_spacing is not None:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
    return font


def qt_palette(p: Palette) -> QPalette:
    """native ウィジェット（QComboBox のポップアップ等）用の QPalette も揃える。"""
    palette = QPalette()
    window = qcolor(p.canvas_bg)
    surface = qcolor(p.panel)
    field = qcolor(p.panel_inset)
    text = qcolor(p.text_body)
    muted = qcolor(p.text_faint)
    accent = qcolor(p.accent)

    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, qcolor(p.text_pri))
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
QWidget {{
    color: {p.text_body};
    font-size: 13px;
}}
QWidget#canvas {{ background-color: {p.canvas_bg}; }}
QWidget#card {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {p.bg_top}, stop:1 {p.bg_bottom});
    border: 1px solid {p.border};
    border-radius: 22px;
}}
QWidget#headerBar {{ background: transparent; border-bottom: 1px solid {p.border_soft}; }}

QLabel {{ background: transparent; }}
QLabel#sectionLabel {{ color: {p.text_faint}; font-size: 11px; font-weight: 600; }}
QLabel#hint {{ color: {p.text_faint}; font-size: 11.5px; }}
QLabel#titlePri {{ color: {p.text_pri}; font-size: 18px; font-weight: 700; }}
QLabel#titleSub {{ color: {p.text_faint}; font-size: 12px; }}
QLabel#liveBadge {{ color: {p.text_faint}; font-size: 11px; }}

QFrame#sectionPanel[variant="panel"] {{
    background-color: {p.panel};
    border: 1px solid {p.border_soft};
    border-radius: 16px;
}}
QFrame#sectionPanel[variant="panelDeep"] {{
    background-color: {p.panel_deep};
    border: 1px solid {p.border_soft};
    border-radius: 16px;
}}

QPushButton {{
    background-color: {p.panel_soft};
    border: 1px solid {p.border_soft};
    border-radius: 9px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
    color: {p.text_muted};
    outline: none;
}}
QPushButton:hover {{ border-color: {p.accent}; color: {p.text_body}; }}
QPushButton:disabled {{ color: {p.text_disabled}; background-color: {p.panel_inset}; border-color: {p.border_soft}; }}

QPushButton#ghost {{
    background-color: transparent;
    border: 1px solid {p.border_soft};
    color: {p.text_muted};
    min-height: 30px;
}}
QPushButton#ghost:hover {{ border-color: {p.accent}; color: {p.text_body}; }}

QPushButton#chip {{
    background-color: {p.accent_soft};
    border: 1px solid {p.accent};
    color: {p.chip_on_text};
    font-weight: 700;
    min-height: 30px;
}}
QPushButton#chip:hover {{ background-color: {p.chip_on_bg}; }}

QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0.4, y2:1, stop:0 {p.accent_grad_top}, stop:1 {p.accent_grad_bottom});
    border: 1px solid {p.accent_grad_bottom};
    color: #FFFFFF;
    font-size: 13.5px;
    font-weight: 700;
    padding: 11px 26px;
    border-radius: 11px;
    min-height: 34px;
}}
QPushButton#primary:hover {{ border-color: {p.accent_hover}; }}
QPushButton#primary:disabled {{ background: {p.panel_inset}; border-color: {p.border_soft}; color: {p.text_disabled}; }}

QPushButton#stepper {{
    background-color: {p.panel_inset};
    border: 1px solid {p.border_soft};
    border-radius: 7px;
    padding: 0;
    font-size: 14px;
    font-weight: 600;
    color: {p.text_muted};
}}
QPushButton#stepper:hover {{ border-color: {p.accent}; color: {p.text_body}; }}
QPushButton#stepper:disabled {{ color: {p.text_disabled}; }}

QPushButton#iconButton {{
    background-color: {p.panel_inset};
    border: 1px solid {p.border_soft};
    border-radius: 9px;
    padding: 0;
    font-size: 14px;
    color: {p.text_muted};
}}
QPushButton#iconButton:hover {{ border-color: {p.accent}; color: {p.text_body}; }}

QPushButton#formatChip {{
    background-color: {p.chip_off_bg};
    border: 1px solid {p.chip_off_border};
    color: {p.chip_off_text};
    font-size: 12px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 9px;
    min-height: 26px;
}}
QPushButton#formatChip:checked {{
    background-color: {p.chip_on_bg};
    border: 1px solid {p.chip_on_border};
    color: {p.chip_on_text};
}}
QPushButton#formatChip:disabled {{ color: {p.text_disabled}; }}

QLineEdit, QComboBox, QSpinBox {{
    background-color: {p.panel_inset};
    border: 1px solid {p.border_soft};
    border-radius: 9px;
    padding: 9px 12px;
    font-size: 12.5px;
    color: {p.text_body};
    selection-background-color: {p.accent_soft};
    selection-color: {p.text_body};
    outline: none;
}}
QLineEdit:read-only {{ color: {p.text_faint}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {p.text_disabled}; }}

QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {p.panel};
    border: 1px solid {p.border_soft};
    selection-background-color: {p.accent_soft};
    selection-color: {p.text_body};
    outline: none;
    padding: 4px;
}}

QPlainTextEdit#log {{
    background-color: transparent;
    border: none;
    color: {p.text_faint};
    font-size: 11.5px;
    padding: 0;
}}

QStatusBar {{ background-color: transparent; color: {p.text_faint}; font-size: 11.5px; }}
QSplitter::handle {{ background-color: transparent; height: 10px; }}

QProgressBar {{
    background-color: {p.panel_inset};
    border: none;
    border-radius: 4px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.accent_grad_top}, stop:1 {p.accent_grad_bottom});
    border-radius: 4px;
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 4px; min-width: 24px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QToolTip {{
    background-color: {p.panel};
    color: {p.text_body};
    border: 1px solid {p.border_soft};
    padding: 4px 6px;
}}
"""


def drop_area_qss(p: Palette, active: bool) -> str:
    """ドロップ領域のスタイル。`active` はドラッグ中の見た目。"""
    background = p.accent_soft if active else p.panel_inset
    border = p.accent if active else p.border_dashed
    return f"""
QFrame#dropArea {{
    background-color: {background};
    border: 2px dashed {border};
    border-radius: 16px;
}}
"""
