"""メイン画面：ドロップ領域・ファイル一覧・ログ・言語・実行バー。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..config import LANGUAGES
from . import styles
from .drop_area import DropArea
from .file_list import FileListPanel
from .styles import Palette
from .widgets import SectionPanel


class MainPage(QWidget):
    """メイン画面。状態は持たず、MainWindow から呼ばれる薄いビュー。"""

    filesDropped = Signal(list)
    dropAreaClicked = Signal()
    addClicked = Signal()
    removeSelectedClicked = Signal()
    clearClicked = Signal()
    rowDoubleClicked = Signal(int)
    startClicked = Signal()
    cancelClicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        self.drop_area = DropArea()
        self.drop_area.filesDropped.connect(self.filesDropped)
        self.drop_area.clicked.connect(self.dropAreaClicked)
        root.addWidget(self.drop_area)

        self.file_list = FileListPanel()
        self.file_list.addClicked.connect(self.addClicked)
        self.file_list.removeSelectedClicked.connect(self.removeSelectedClicked)
        self.file_list.clearClicked.connect(self.clearClicked)
        self.file_list.rowDoubleClicked.connect(self.rowDoubleClicked)

        self._log_panel = self._build_log_panel()

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.file_list)
        splitter.addWidget(self._log_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 150])
        root.addWidget(splitter, 1)

        root.addWidget(self._build_language_panel())
        root.addLayout(self._build_run_bar())

    # ------------------------------------------------------------------ ログ

    def _build_log_panel(self) -> SectionPanel:
        panel = SectionPanel("ログ", variant="panelDeep")
        panel.setMinimumHeight(90)
        self._log = QPlainTextEdit()
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        panel.body.addWidget(self._log)
        return panel

    def append_log(self, message: str) -> None:
        self._log.appendPlainText(message)

    # ------------------------------------------------------------------ 言語

    def _build_language_panel(self) -> SectionPanel:
        panel = SectionPanel("言語")
        self.language_combo = QComboBox()
        self.language_combo.setMaximumWidth(280)
        for label, code in LANGUAGES:
            self.language_combo.addItem(label, code)
        row = QHBoxLayout()
        row.addWidget(self.language_combo)
        row.addStretch(1)
        panel.body.addLayout(row)

        note = QLabel("モデル・話者分離・出力形式は設定 ⚙ から変更できます")
        note.setObjectName("hint")
        panel.body.addWidget(note)
        return panel

    # ------------------------------------------------------------------ 実行バー

    def _build_run_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(16)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)

        self._percent_label = QLabel("0%")
        self._percent_label.setFont(styles.mono_font(12))
        self._percent_label.setMinimumWidth(34)

        self.cancel_button = QPushButton("中止")
        self.cancel_button.setObjectName("ghost")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setFocusPolicy(Qt.NoFocus)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancelClicked)

        self.start_button = QPushButton("文字起こしを開始")
        self.start_button.setObjectName("primary")
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.setFocusPolicy(Qt.NoFocus)
        self.start_button.clicked.connect(self.startClicked)

        bar.addWidget(self.progress_bar, 1)
        bar.addWidget(self._percent_label)
        bar.addWidget(self.cancel_button)
        bar.addWidget(self.start_button)
        return bar

    def set_progress(self, percent: int) -> None:
        self.progress_bar.setValue(percent)
        self._percent_label.setText(f"{percent}%")

    # ------------------------------------------------------------------ テーマ

    def set_palette(self, palette: Palette) -> None:
        self.drop_area.set_palette(palette)
        self.file_list.set_palette(palette)
        self._percent_label.setStyleSheet(f"color: {palette.text_muted};")
