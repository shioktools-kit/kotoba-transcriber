"""デザインで繰り返し使う小さな部品。ロジックは持たず見た目だけ担当する。"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import styles
from .styles import Palette, qcolor


def apply_drop_shadow(widget: QWidget, palette: Palette) -> None:
    """カード外枠の box-shadow に相当するもの。"""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(palette.shadow_blur)
    effect.setOffset(0, palette.shadow_y)
    effect.setColor(qcolor(palette.shadow_color))
    widget.setGraphicsEffect(effect)


class SectionPanel(QFrame):
    """角丸16pxのカードパネル。上に小見出し、下に本文レイアウトを持つ。"""

    def __init__(self, title: str = "", *, variant: str = "panel", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionPanel")
        self.setProperty("variant", variant)
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        if title:
            label = QLabel(title)
            label.setObjectName("sectionLabel")
            label.setFont(styles.ui_font(11, QFont.Weight.DemiBold, letter_spacing=1.2))
            outer.addWidget(label)

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body)


class WaveformLogo(QWidget):
    """44x44 の角丸グラデーションロゴ。5 本の波形バーを描く。"""

    _BAR_HEIGHTS = (10, 18, 24, 14, 8)
    _BAR_ALPHAS = (0.85, 0.95, 1.0, 0.9, 0.8)

    def __init__(self, palette: Palette, parent=None) -> None:
        super().__init__(parent)
        self._palette = palette
        self.setFixedSize(44, 44)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor(self._palette.accent_grad_top))
        gradient.setColorAt(1.0, QColor(self._palette.accent_grad_bottom))
        painter.fillPath(path, gradient)

        bar_width = 3
        gap = 3
        total = bar_width * len(self._BAR_HEIGHTS) + gap * (len(self._BAR_HEIGHTS) - 1)
        x = (self.width() - total) / 2
        center_y = self.height() / 2

        for height, alpha in zip(self._BAR_HEIGHTS, self._BAR_ALPHAS):
            bar_rect = QRectF(x, center_y - height / 2, bar_width, height)
            bar_path = QPainterPath()
            bar_path.addRoundedRect(bar_rect, 1.5, 1.5)
            painter.fillPath(bar_path, QColor(255, 255, 255, int(round(alpha * 255))))
            x += bar_width + gap


class ToggleSwitch(QPushButton):
    """38x22 のトグルスイッチ。QPushButton(checkable) をカスタム描画する。"""

    def __init__(self, palette: Palette, parent=None) -> None:
        super().__init__(parent)
        self._palette = palette
        self.setCheckable(True)
        self.setFixedSize(38, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("toggleSwitch")
        # デフォルトの QPushButton QSS を打ち消し、paintEvent だけで描く。
        self.setStyleSheet("QPushButton#toggleSwitch { border: none; background: transparent; }")

        self.setFocusPolicy(Qt.NoFocus)
        self._knob_x = 2.0
        self._anim = QPropertyAnimation(self, b"knobX", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate_to_state)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def _get_knob_x(self) -> float:
        return self._knob_x

    def _set_knob_x(self, value: float) -> None:
        self._knob_x = value
        self.update()

    knobX = Property(float, _get_knob_x, _set_knob_x)

    def _animate_to_state(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob_x)
        self._anim.setEndValue(18.0 if checked else 2.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 - Qt override
        super().setChecked(checked)
        self._knob_x = 18.0 if checked else 2.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        p = self._palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        track_rect = QRectF(0, 0, self.width(), self.height())
        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, 11, 11)

        if not self.isEnabled():
            track_color = qcolor(p.panel_inset)
        elif self.isChecked():
            track_color = qcolor(p.accent)
        else:
            track_color = qcolor(p.panel_inset)
        painter.fillPath(track_path, track_color)

        if not self.isChecked() or not self.isEnabled():
            painter.setPen(qcolor(p.border_soft))
            painter.drawPath(track_path)

        knob_color = QColor("#FFFFFF") if self.isEnabled() else qcolor(p.text_disabled)
        knob_rect = QRectF(self._knob_x, 2, 18, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_rect)


class SegmentedControl(QWidget):
    """3 択程度のピル型セグメントコントロール（外観テーマの切り替えなど）。"""

    valueChanged = Signal(str)

    def __init__(self, options: list[tuple[str, str]], palette: Palette, parent=None) -> None:
        super().__init__(parent)
        self._palette = palette
        self._options = options
        self._value = options[0][1] if options else ""

        self.setObjectName("segmentedControl")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for label, value in options:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setFlat(True)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _checked, v=value: self._select(v))
            self._group.addButton(button)
            layout.addWidget(button)
            self._buttons[value] = button

        self.set_palette(palette)
        self.set_value(self._value)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.setStyleSheet(
            f"QWidget#segmentedControl {{ background-color: {palette.seg_track_bg}; "
            f"border: 1px solid {palette.border_soft}; border-radius: 11px; }}"
        )
        self._restyle_buttons()

    def _restyle_buttons(self) -> None:
        p = self._palette
        for value, button in self._buttons.items():
            selected = value == self._value
            bg = p.seg_selected_bg if selected else "transparent"
            fg = p.seg_selected_text if selected else p.seg_text
            weight = 700 if selected else 600
            button.setStyleSheet(
                "QPushButton {"
                f"padding: 6px 12px; border-radius: 9px; border: none;"
                f"font-size: 11.5px; font-weight: {weight};"
                f"color: {fg}; background-color: {bg};"
                "}"
            )

    def _select(self, value: str) -> None:
        if value == self._value:
            return
        self._value = value
        self._restyle_buttons()
        self.valueChanged.emit(value)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        if value not in self._buttons:
            return
        self._value = value
        self._buttons[value].setChecked(True)
        self._restyle_buttons()


class Stepper(QWidget):
    """−／値／＋ の話者数ステッパー。QSpinBox 相当の value()/setValue() を持つ。"""

    valueChanged = Signal(int)

    def __init__(
        self,
        minimum: int = 0,
        maximum: int = 20,
        *,
        zero_label: str = "自動推定",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._zero_label = zero_label
        self._value = minimum

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._minus = QPushButton("−")
        self._minus.setObjectName("stepper")
        self._minus.setFixedSize(24, 24)
        self._minus.setCursor(Qt.PointingHandCursor)
        self._minus.setFocusPolicy(Qt.NoFocus)
        self._minus.clicked.connect(lambda: self.set_value(self._value - 1))

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setMinimumWidth(56)

        self._plus = QPushButton("＋")
        self._plus.setObjectName("stepper")
        self._plus.setFixedSize(24, 24)
        self._plus.setCursor(Qt.PointingHandCursor)
        self._plus.setFocusPolicy(Qt.NoFocus)
        self._plus.clicked.connect(lambda: self.set_value(self._value + 1))

        layout.addWidget(self._minus)
        layout.addWidget(self._label)
        layout.addWidget(self._plus)

        self._update_label()

    def set_palette(self, palette: Palette) -> None:
        self._label.setFont(styles.mono_font(12))
        self._label.setStyleSheet(f"color: {palette.text_body};")
        self._label.setFont(styles.mono_font(12))

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        value = max(self._minimum, min(self._maximum, value))
        if value == self._value:
            return
        self._value = value
        self._update_label()
        self.valueChanged.emit(value)

    def _update_label(self) -> None:
        self._label.setText(self._zero_label if self._value == 0 else str(self._value))
        self._minus.setEnabled(self._value > self._minimum)
        self._plus.setEnabled(self._value < self._maximum)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 - Qt override
        super().setEnabled(enabled)
        self._minus.setEnabled(enabled and self._value > self._minimum)
        self._plus.setEnabled(enabled and self._value < self._maximum)


class FlowLayout(QLayout):
    """左から右へ詰め、収まらなければ次の行へ折り返すレイアウト。

    Qt に標準の flow layout が無いための実装（公式サンプルの PySide6 移植）。
    出力形式のチップ群など、`flex-wrap: wrap` に相当する箇所で使う。
    """

    def __init__(self, parent=None, margin: int = 0, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item) -> None:  # noqa: N802 - Qt override
        self._items.append(item)

    def count(self) -> int:  # noqa: N802 - Qt override
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802 - Qt override
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: N802 - Qt override
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:  # noqa: N802 - Qt override
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt override
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt override
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 - Qt override
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y = effective.x(), effective.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()


class Chip(QPushButton):
    """✓ / + の接頭辞が付く、チェック可能なピル型ボタン（出力形式など）。"""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self._label = label
        self.setObjectName("formatChip")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.toggled.connect(self._update_text)
        self._update_text(False)

    def _update_text(self, checked: bool) -> None:
        mark = "✓" if checked else "+"
        self.setText(f"{mark} {self._label}")


class HeaderBar(QWidget):
    """ロゴ・タイトル・ライブバッジ・戻る/設定ボタン。"""

    backClicked = Signal()
    gearClicked = Signal()

    def __init__(self, palette: Palette, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("headerBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._palette = palette

        layout = QHBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        self._back_button = QPushButton("←")
        self._back_button.setObjectName("iconButton")
        self._back_button.setFixedSize(30, 30)
        self._back_button.setCursor(Qt.PointingHandCursor)
        self._back_button.setFocusPolicy(Qt.NoFocus)
        self._back_button.clicked.connect(self.backClicked)
        self._back_button.hide()

        self._logo = WaveformLogo(palette)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._title_label = QLabel()
        self._title_label.setObjectName("titlePri")
        self._subtitle_label = QLabel()
        self._subtitle_label.setObjectName("titleSub")
        title_col.addWidget(self._title_label)
        title_col.addWidget(self._subtitle_label)

        layout.addWidget(self._back_button)
        layout.addWidget(self._logo)
        layout.addLayout(title_col)
        layout.addStretch(1)

        self._live_dot = QFrame()
        self._live_dot.setFixedSize(6, 6)
        self._live_dot.setAttribute(Qt.WA_StyledBackground, True)
        self._live_label = QLabel("ローカル処理 · 送信されません")
        self._live_label.setObjectName("liveBadge")
        live_row = QHBoxLayout()
        live_row.setSpacing(6)
        live_row.addWidget(self._live_dot)
        live_row.addWidget(self._live_label)
        layout.addLayout(live_row)

        self._gear_button = QPushButton("⚙")
        self._gear_button.setObjectName("iconButton")
        self._gear_button.setFixedSize(30, 30)
        self._gear_button.setCursor(Qt.PointingHandCursor)
        self._gear_button.setFocusPolicy(Qt.NoFocus)
        self._gear_button.setToolTip("設定")
        self._gear_button.clicked.connect(self.gearClicked)
        layout.addWidget(self._gear_button)

        self.set_mode(is_settings=False)
        self.set_palette(palette)

    def set_mode(self, *, is_settings: bool) -> None:
        self._back_button.setVisible(is_settings)
        self._gear_button.setVisible(not is_settings)
        if is_settings:
            self._title_label.setText("設定")
            self._subtitle_label.setText("モデル・話者分離・出力の設定")
        else:
            self._title_label.setText("Kotoba Transcriber")
            self._subtitle_label.setText("kotoba-whisper ローカル文字起こし")

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._logo.set_palette(palette)
        self._live_dot.setStyleSheet(
            f"background-color: {palette.success}; border-radius: 3px;"
        )
