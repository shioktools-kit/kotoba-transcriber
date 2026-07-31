"""ファイル一覧パネル。行ごとにステータスバッジと進捗バーを持つ。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import styles
from .styles import Palette
from .widgets import SectionPanel


@dataclass(frozen=True)
class RowStatusStyle:
    bg: str
    fg: str
    bar: str


def _status_style(palette: Palette, status: str) -> RowStatusStyle:
    mapping = {
        "完了": RowStatusStyle(palette.success_soft, palette.success_text, palette.success),
        "処理中": RowStatusStyle(palette.accent_soft, palette.accent, palette.accent),
        "待機": RowStatusStyle(palette.panel_inset, palette.text_faint, palette.text_faint),
        "エラー": RowStatusStyle(palette.danger_soft, palette.danger_text, palette.danger),
    }
    return mapping.get(status, mapping["待機"])


class FileRow(QFrame):
    """ファイル一覧の 1 行。"""

    clicked = Signal(int, object)  # index, Qt.KeyboardModifiers
    doubleClicked = Signal(int)

    def __init__(self, index: int, parent=None) -> None:
        super().__init__(parent)
        self._index = index
        self.setObjectName("fileRow")
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 10, 6, 10)
        layout.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._name_label = _elide_label(bold=True)
        self._path_label = _elide_label(bold=False)
        text_col.addWidget(self._name_label)
        text_col.addWidget(self._path_label)
        text_wrap = QWidget()
        text_wrap.setLayout(text_col)
        layout.addWidget(text_wrap, 1)

        self._duration_label = QLabel()
        self._duration_label.setFixedWidth(64)
        self._duration_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._duration_label.setFont(styles.mono_font(12))
        layout.addWidget(self._duration_label)

        badge_wrap = QWidget()
        badge_wrap.setFixedWidth(78)
        badge_layout = QHBoxLayout(badge_wrap)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setAlignment(Qt.AlignCenter)
        self._status_badge = QLabel()
        self._status_badge.setAlignment(Qt.AlignCenter)
        self._status_badge.setFont(styles.ui_font(11, QFont.Weight.DemiBold))
        badge_layout.addWidget(self._status_badge)
        layout.addWidget(badge_wrap)

        progress_wrap = QWidget()
        progress_wrap.setFixedWidth(120)
        progress_layout = QHBoxLayout(progress_wrap)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)
        self._bar_track = QFrame()
        self._bar_track.setFixedHeight(5)
        self._bar_track.setAttribute(Qt.WA_StyledBackground, True)
        bar_track_layout = QHBoxLayout(self._bar_track)
        bar_track_layout.setContentsMargins(0, 0, 0, 0)
        bar_track_layout.setSpacing(0)
        self._bar_fill = QFrame()
        self._bar_fill.setFixedHeight(5)
        self._bar_fill.setAttribute(Qt.WA_StyledBackground, True)
        bar_track_layout.addWidget(self._bar_fill, 0, Qt.AlignLeft)
        bar_track_layout.addStretch(1)
        progress_layout.addWidget(self._bar_track, 1)
        self._progress_label = QLabel()
        self._progress_label.setFixedWidth(34)
        self._progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._progress_label.setFont(styles.mono_font(11.5))
        progress_layout.addWidget(self._progress_label)
        layout.addWidget(progress_wrap)

        self._selected = False

    def set_index(self, index: int) -> None:
        self._index = index

    def set_selected(self, selected: bool, palette: Palette) -> None:
        self._selected = selected
        self._apply_container_style(palette)

    def _apply_container_style(self, palette: Palette) -> None:
        bg = palette.accent_soft if self._selected else "transparent"
        self.setStyleSheet(
            f"QFrame#fileRow {{ background-color: {bg}; border: none; "
            f"border-top: 1px solid {palette.border_soft}; border-radius: 8px; }}"
        )

    def update_content(self, name: str, sub: str, sub_is_error: bool, duration: str,
                        status: str, progress: float, palette: Palette) -> None:
        self._name_label.setText(name)
        self._name_label.setToolTip(name)
        self._name_label.setStyleSheet(f"color: {palette.text_body};")
        self._name_label.setFont(styles.ui_font(13, QFont.Weight.DemiBold))

        self._path_label.setText(sub)
        self._path_label.setToolTip(sub)
        sub_color = palette.danger_text if sub_is_error else palette.text_faint
        self._path_label.setStyleSheet(f"color: {sub_color};")
        self._path_label.setFont(styles.ui_font(11))

        self._duration_label.setText(duration)
        self._duration_label.setStyleSheet(f"color: {palette.text_sec};")

        style = _status_style(palette, status)
        self._status_badge.setText(status)
        self._status_badge.setStyleSheet(
            f"background-color: {style.bg}; color: {style.fg}; "
            "border-radius: 7px; padding: 3px 10px;"
        )

        percent = max(0, min(100, round(progress * 100)))
        width = max(0, round(self._bar_track.width() * percent / 100)) if self._bar_track.width() else 0
        self._bar_track.setStyleSheet(
            f"background-color: {palette.panel_inset}; border-radius: 3px;"
        )
        self._bar_fill.setFixedWidth(max(2, width) if percent else 0)
        self._bar_fill.setStyleSheet(f"background-color: {style.bar}; border-radius: 3px;")
        self._progress_label.setText(f"{percent}%")
        self._progress_label.setStyleSheet(f"color: {palette.text_faint};")

        self._apply_container_style(palette)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        # 幅が確定してから進捗バーの塗り幅を再計算させる。
        text = self._progress_label.text()
        if text.endswith("%"):
            try:
                percent = int(text[:-1])
            except ValueError:
                percent = 0
            width = max(0, round(self._bar_track.width() * percent / 100))
            self._bar_fill.setFixedWidth(max(2, width) if percent else 0)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._index, event.modifiers())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self._index)
        super().mouseDoubleClickEvent(event)


def _elide_label(*, bold: bool) -> QLabel:
    label = QLabel()
    metrics_policy = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    label.setSizePolicy(metrics_policy)
    return label


class FileListPanel(SectionPanel):
    """ヘッダー（追加・削除・クリア）＋ スクロール可能な行一覧。"""

    addClicked = Signal()
    removeSelectedClicked = Signal()
    clearClicked = Signal()
    rowDoubleClicked = Signal(int)
    selectionChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("ファイル", variant="panel", parent=parent)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._add_button = QPushButton("ファイルを追加")
        self._add_button.setObjectName("chip")
        self._add_button.setCursor(Qt.PointingHandCursor)
        self._add_button.setFocusPolicy(Qt.NoFocus)
        self._add_button.clicked.connect(self.addClicked)

        self._remove_button = QPushButton("選択を削除")
        self._remove_button.setObjectName("ghost")
        self._remove_button.setCursor(Qt.PointingHandCursor)
        self._remove_button.setFocusPolicy(Qt.NoFocus)
        self._remove_button.clicked.connect(self.removeSelectedClicked)

        self._clear_button = QPushButton("すべてクリア")
        self._clear_button.setObjectName("ghost")
        self._clear_button.setCursor(Qt.PointingHandCursor)
        self._clear_button.setFocusPolicy(Qt.NoFocus)
        self._clear_button.clicked.connect(self.clearClicked)

        self._hint_label = QLabel("行をダブルクリックで出力を開く")
        self._hint_label.setObjectName("hint")

        header.addStretch(1)
        header.addWidget(self._add_button)
        header.addWidget(self._remove_button)
        header.addWidget(self._clear_button)
        header.addWidget(self._hint_label)

        # 素の QHBoxLayout のまま addLayout() すると、パネル全体の高さが
        # 足りないときにこの行だけ数 px まで潰れて中のボタンが溢れて重なる
        # （ボタン自身の min-height はレイアウト側の最小サイズ計算に
        # 伝わらない）。QWidget で包んで明示的に高さの下限を持たせることで、
        # 親レイアウトのボトムアップな最小サイズ計算に正しく参加させる。
        header_widget = QWidget()
        header_widget.setLayout(header)
        header_widget.setMinimumHeight(46)
        self.body.addWidget(header_widget)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setMinimumHeight(160)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_container)
        self.body.addWidget(self._scroll, 1)

        self._empty_label = QLabel("ファイルがありません")
        self._empty_label.setAlignment(Qt.AlignCenter)

        self._rows: list[FileRow] = []
        self._selected: set[int] = set()
        self._anchor: int | None = None
        self._palette = styles.LIGHT

    # ------------------------------------------------------------ 公開 API

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._empty_label.setStyleSheet(f"color: {palette.text_faint}; padding: 24px;")
        for row in self._rows:
            row._apply_container_style(palette)  # noqa: SLF001 - 同一パッケージ内の内部利用

    def set_items(self, items: list) -> None:
        """一覧全体を作り直す（追加・削除・クリア時に呼ぶ）。"""
        self._selected &= {i for i in range(len(items))}

        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # deleteLater() だけだと次のイベントループまで見た目に残り、
                # 新しい行と一瞬重なって描画される。即座に切り離しておく。
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._rows.clear()

        if not items:
            self._list_layout.insertWidget(0, self._empty_label)
            self.selectionChanged.emit()
            return

        for index, file_item in enumerate(items):
            row = self._make_row(index)
            self._list_layout.insertWidget(index, row)
            self._rows.append(row)
            self._refresh_row(index, file_item)
        self.selectionChanged.emit()

    def update_row(self, index: int, file_item) -> None:
        """1 行だけ更新する（進捗・状態の更新用）。"""
        if 0 <= index < len(self._rows):
            self._refresh_row(index, file_item)

    def selected_indices(self) -> list[int]:
        return sorted(self._selected)

    def clear_selection(self) -> None:
        self._selected.clear()
        for row in self._rows:
            row.set_selected(False, self._palette)
        self.selectionChanged.emit()

    def set_controls_enabled(self, enabled: bool) -> None:
        self._add_button.setEnabled(enabled)
        self._remove_button.setEnabled(enabled)
        self._clear_button.setEnabled(enabled)

    def scroll_to(self, index: int) -> None:
        if 0 <= index < len(self._rows):
            self._scroll.ensureWidgetVisible(self._rows[index])

    # ------------------------------------------------------------ 内部処理

    def _make_row(self, index: int) -> FileRow:
        row = FileRow(index)
        row.clicked.connect(self._on_row_clicked)
        row.doubleClicked.connect(self.rowDoubleClicked)
        return row

    def _refresh_row(self, index: int, file_item) -> None:
        row = self._rows[index]
        row.set_index(index)
        sub = file_item.error or str(file_item.path)
        duration = _format_duration(file_item.duration)
        row.update_content(
            file_item.path.name,
            sub,
            bool(file_item.error),
            duration,
            file_item.status,
            file_item.progress,
            self._palette,
        )
        row.set_selected(index in self._selected, self._palette)

    def _on_row_clicked(self, index: int, modifiers) -> None:
        if modifiers & Qt.ControlModifier:
            if index in self._selected:
                self._selected.discard(index)
            else:
                self._selected.add(index)
            self._anchor = index
        elif modifiers & Qt.ShiftModifier and self._anchor is not None:
            lo, hi = sorted((self._anchor, index))
            self._selected = set(range(lo, hi + 1))
        else:
            self._selected = {index}
            self._anchor = index

        for row_index, row in enumerate(self._rows):
            row.set_selected(row_index in self._selected, self._palette)
        self.selectionChanged.emit()


def _format_duration(seconds: float) -> str:
    if not seconds:
        return "-"
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
