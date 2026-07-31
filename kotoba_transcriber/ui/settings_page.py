"""設定画面：外観・モデル・話者分離・出力設定。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    APP_NAME,
    DEFAULT_MODEL_ID,
    MODELS,
    OUTPUT_FORMATS,
    OutputOptions,
    model_for,
)
from ..diarization import is_available as diarization_available
from . import styles
from .styles import Palette
from .widgets import Chip, FlowLayout, SectionPanel, SegmentedControl, Stepper, ToggleSwitch

# モデル一覧の末尾に置く「その他」項目の目印。
_CUSTOM_MODEL = "__custom__"


class SettingsPage(QWidget):
    """外観・モデル・話者分離・出力の 4 パネル。値の保持と入出力だけを担当する。"""

    themeChanged = Signal(str)
    changed = Signal()  # 開始ボタンの有効/無効判定などに使う、まとめの変更通知

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._palette = styles.LIGHT
        self._model_index = 0
        self._format_chips: dict[str, Chip] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        root.addWidget(self._build_appearance_panel())
        root.addWidget(self._build_model_panel())
        root.addWidget(self._build_diarization_panel())
        root.addWidget(self._build_output_panel())
        root.addStretch(1)

    # ------------------------------------------------------------------ 外観

    def _build_appearance_panel(self) -> SectionPanel:
        panel = SectionPanel("外観")
        self._theme_control = SegmentedControl(list(styles.THEME_LABELS), self._palette)
        self._theme_control.valueChanged.connect(self.themeChanged)
        row = QHBoxLayout()
        row.addWidget(self._theme_control)
        row.addStretch(1)
        panel.body.addLayout(row)
        return panel

    def theme(self) -> str:
        return self._theme_control.value()

    def set_theme(self, value: str) -> None:
        self._theme_control.set_value(value)

    # ------------------------------------------------------------------ モデル

    def _build_model_panel(self) -> SectionPanel:
        panel = SectionPanel("モデル")

        # 編集可能にすると文字部分のクリックがカーソル移動になり、
        # 言語・テーマと違ってドロップダウンが開かない。モデル ID の直接入力は
        # 末尾の「その他」項目から行う。
        self._model_combo = QComboBox()
        self._model_combo.setMaximumWidth(360)
        self._model_combo.setToolTip(
            "一覧から選ぶか、「その他」で Hugging Face のモデル ID を直接指定できます"
        )
        for choice in MODELS:
            self._model_combo.addItem(choice.label, choice.model_id)
        self._model_combo.addItem("その他（モデル ID を直接入力）...", _CUSTOM_MODEL)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        row = QHBoxLayout()
        row.addWidget(self._model_combo)
        row.addStretch(1)
        panel.body.addLayout(row)

        self._model_note = QLabel("")
        self._model_note.setObjectName("hint")
        self._model_note.setWordWrap(True)
        panel.body.addWidget(self._model_note)

        return panel

    def _on_model_changed(self, _index: int = -1) -> None:
        if self._model_combo.currentData() == _CUSTOM_MODEL:
            self._ask_custom_model()
            return
        self._model_index = self._model_combo.currentIndex()
        self._update_model_note()
        self.changed.emit()

    def _update_model_note(self) -> None:
        choice = model_for(self.current_model_id())
        self._model_note.setText(
            f"{choice.note}　|　chunk {choice.chunk_length_s:.0f}s / batch {choice.batch_size}"
        )

    def _ask_custom_model(self) -> None:
        model_id, accepted = QInputDialog.getText(
            self,
            APP_NAME,
            "Hugging Face のモデル ID を入力してください。\n"
            "（例: openai/whisper-large-v3-turbo）",
        )
        model_id = model_id.strip() if accepted else ""
        if not model_id:
            self._select_model_index(self._model_index)
            return
        self.select_model(model_id)

    def current_model_id(self) -> str:
        data = self._model_combo.currentData()
        if not data or data == _CUSTOM_MODEL:
            return DEFAULT_MODEL_ID
        return str(data)

    def select_model(self, model_id: str) -> None:
        """モデル ID を選択する。一覧にない ID なら項目として足す。"""
        index = self._model_combo.findData(model_id)
        if index < 0:
            index = self._model_combo.count() - 1  # 「その他」の手前へ
            self._model_combo.blockSignals(True)
            self._model_combo.insertItem(index, model_id, model_id)
            self._model_combo.blockSignals(False)
        self._select_model_index(index)

    def _select_model_index(self, index: int) -> None:
        index = max(0, min(index, self._model_combo.count() - 1))
        self._model_combo.blockSignals(True)
        self._model_combo.setCurrentIndex(index)
        self._model_combo.blockSignals(False)
        self._model_index = index
        self._update_model_note()
        self.changed.emit()

    # ------------------------------------------------------------------ 話者分離

    def _build_diarization_panel(self) -> SectionPanel:
        panel = SectionPanel("話者分離")
        available = diarization_available()

        toggle_row = QHBoxLayout()
        label = QLabel("話者分離を行う")
        label.setFont(styles.ui_font(13, QFont.Weight.DemiBold))
        self._diarize_toggle = ToggleSwitch(self._palette)
        self._diarize_toggle.setEnabled(available)
        self._diarize_toggle.toggled.connect(self._sync_diarization_controls)
        toggle_row.addWidget(label)
        toggle_row.addStretch(1)
        toggle_row.addWidget(self._diarize_toggle)
        panel.body.addLayout(toggle_row)

        speaker_row = QHBoxLayout()
        speaker_label = QLabel("話者数")
        self._speaker_stepper = Stepper(0, 20)
        self._speaker_stepper.set_palette(self._palette)
        speaker_row.addWidget(speaker_label)
        speaker_row.addStretch(1)
        speaker_row.addWidget(self._speaker_stepper)
        panel.body.addLayout(speaker_row)

        note_text = (
            "Hugging Face のトークンと利用条件への同意が必要です"
            if available
            else "pyannote.audio が入っていません。setup.bat を実行し直してください。"
        )
        self._diarize_note = QLabel(note_text)
        self._diarize_note.setObjectName("hint")
        self._diarize_note.setWordWrap(True)
        panel.body.addWidget(self._diarize_note)

        self._diarize_label = label
        self._speaker_label = speaker_label
        self._sync_diarization_controls()
        return panel

    def _sync_diarization_controls(self, *_args) -> None:
        enabled = self._diarize_toggle.isChecked() and self._diarize_toggle.isEnabled()
        self._speaker_stepper.setEnabled(enabled)
        self.changed.emit()

    def diarization_enabled(self) -> bool:
        return self._diarize_toggle.isChecked() and self._diarize_toggle.isEnabled()

    def diarization_available(self) -> bool:
        return diarization_available()

    def num_speakers(self) -> int:
        return self._speaker_stepper.value()

    def set_diarization(self, enabled: bool, num_speakers: int) -> None:
        self._diarize_toggle.setChecked(enabled and diarization_available())
        self._speaker_stepper.set_value(num_speakers)
        self._sync_diarization_controls()

    # ------------------------------------------------------------------ 出力設定

    def _build_output_panel(self) -> SectionPanel:
        panel = SectionPanel("出力設定")

        chips_widget = QWidget()
        chips_layout = FlowLayout(chips_widget, spacing=8)
        for attribute, label, _suffix in OUTPUT_FORMATS:
            chip = Chip(label)
            chip.toggled.connect(lambda _checked: self.changed.emit())
            chips_layout.addWidget(chip)
            self._format_chips[attribute] = chip
        panel.body.addWidget(chips_widget)

        destination = QHBoxLayout()
        destination.setSpacing(10)
        self._same_folder_chip = Chip("入力と同じフォルダへ出力")
        self._same_folder_chip.toggled.connect(self._on_same_folder_toggled)
        self._output_edit = QLineEdit()
        self._output_edit.setReadOnly(True)
        self._output_edit.setPlaceholderText("出力先フォルダを選択")
        self._output_button = QPushButton("参照...")
        self._output_button.setObjectName("ghost")
        self._output_button.setCursor(Qt.PointingHandCursor)
        self._output_button.setFocusPolicy(Qt.NoFocus)
        self._output_button.clicked.connect(self._browse_output_dir)
        destination.addWidget(self._same_folder_chip)
        destination.addWidget(self._output_edit, 1)
        destination.addWidget(self._output_button)
        panel.body.addLayout(destination)

        return panel

    def _on_same_folder_toggled(self, _checked: bool) -> None:
        self._sync_output_controls()
        self.changed.emit()

    def _sync_output_controls(self) -> None:
        use_same_folder = self._same_folder_chip.isChecked()
        self._output_edit.setEnabled(not use_same_folder)
        self._output_button.setEnabled(not use_same_folder)

    def _browse_output_dir(self) -> None:
        current = self._output_edit.text()
        directory = QFileDialog.getExistingDirectory(self, "出力先フォルダを選択", current)
        if directory:
            self.set_output_dir(directory)
            self._same_folder_chip.setChecked(False)
            self.changed.emit()

    def set_output_dir(self, directory: str) -> None:
        self._output_edit.setText(directory)
        self._output_edit.setCursorPosition(0)
        self._output_edit.setToolTip(directory)

    def output_dir_text(self) -> str:
        return self._output_edit.text()

    def current_options(self) -> OutputOptions:
        from pathlib import Path

        output_dir = None
        if not self._same_folder_chip.isChecked() and self._output_edit.text():
            output_dir = Path(self._output_edit.text())
        options = OutputOptions(output_dir=output_dir)
        for attribute, chip in self._format_chips.items():
            setattr(options, attribute, chip.isChecked())
        return options

    def set_output_formats(self, values: dict[str, bool]) -> None:
        for attribute, chip in self._format_chips.items():
            chip.setChecked(values.get(attribute, False))

    def set_same_folder(self, value: bool) -> None:
        self._same_folder_chip.setChecked(value)
        self._sync_output_controls()

    def same_folder(self) -> bool:
        return self._same_folder_chip.isChecked()

    # ------------------------------------------------------------------ 共通

    def set_enabled_all(self, enabled: bool) -> None:
        """処理中は設定を変えられないようにする。"""
        self._model_combo.setEnabled(enabled)
        if diarization_available():
            self._diarize_toggle.setEnabled(enabled)
        self._speaker_stepper.setEnabled(enabled and self.diarization_enabled())
        for chip in self._format_chips.values():
            chip.setEnabled(enabled)
        self._same_folder_chip.setEnabled(enabled)
        self._sync_output_controls()
        if not enabled:
            self._output_edit.setEnabled(False)
            self._output_button.setEnabled(False)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._theme_control.set_palette(palette)
        self._diarize_toggle.set_palette(palette)
        self._speaker_stepper.set_palette(palette)
        for label in (self._diarize_label, self._speaker_label):
            label.setStyleSheet(f"color: {palette.text_body};")
