"""メインウィンドウ。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTime, Slot
from PySide6.QtGui import QCloseEvent, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..audio import collect_media_files, probe_duration
from ..config import (
    APP_NAME,
    DEFAULT_MODEL_ID,
    FILE_DIALOG_FILTER,
    LANGUAGES,
    MEDIA_EXTENSIONS,
    MODELS,
    ORG_NAME,
    OUTPUT_FORMATS,
    DiarizationOptions,
    OutputOptions,
    model_for,
)
from ..diarization import Diarizer, is_available as diarization_available
from ..formatters import format_timestamp
from ..transcriber import Transcriber
from ..worker import TranscribeWorker
from . import styles
from .drop_area import DropArea

_COL_NAME, _COL_DURATION, _COL_STATUS, _COL_PROGRESS = range(4)

# モデル一覧の末尾に置く「その他」項目の目印。
_CUSTOM_MODEL = "__custom__"

_STATUS_WAITING = "待機"
_STATUS_RUNNING = "処理中"
_STATUS_DONE = "完了"
_STATUS_ERROR = "エラー"


@dataclass
class FileItem:
    path: Path
    duration: float = 0.0
    status: str = _STATUS_WAITING
    progress: float = 0.0
    outputs: list[str] = field(default_factory=list)
    error: str = ""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(980, 960)

        self._items: list[FileItem] = []
        self._transcriber = Transcriber()
        self._diarizer = Diarizer()
        self._thread: QThread | None = None
        self._worker: TranscribeWorker | None = None
        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._theme = styles.THEME_SYSTEM
        self._palette = styles.LIGHT
        self._format_checks: dict[str, QCheckBox] = {}
        self._model_index = 0

        self._build_ui()
        self._restore_settings()
        self._apply_theme()
        self._sync_controls()

        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 10)
        root.setSpacing(10)

        self._drop_area = DropArea()
        self._drop_area.filesDropped.connect(self._add_paths)
        self._drop_area.clicked.connect(self._browse_files)
        root.addWidget(self._drop_area)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._build_file_panel())
        splitter.addWidget(self._build_log_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 170])
        root.addWidget(splitter, 1)

        root.addWidget(self._build_model_panel())

        lower = QHBoxLayout()
        lower.setSpacing(10)
        lower.addWidget(self._build_diarization_panel())
        lower.addWidget(self._build_output_panel(), 1)
        root.addLayout(lower)

        root.addLayout(self._build_run_bar())

        self.setCentralWidget(central)
        self.statusBar().showMessage("ファイルを追加してください")

    def _build_file_panel(self) -> QWidget:
        panel = QGroupBox("ファイル")
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["ファイル", "長さ", "状態", "進捗"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.itemDoubleClicked.connect(self._open_result)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(_COL_NAME, QHeaderView.Stretch)
        for column in (_COL_DURATION, _COL_STATUS, _COL_PROGRESS):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self._table.setColumnWidth(_COL_DURATION, 90)
        self._table.setColumnWidth(_COL_STATUS, 80)
        self._table.setColumnWidth(_COL_PROGRESS, 80)
        layout.addWidget(self._table)

        buttons = QHBoxLayout()
        self._add_button = QPushButton("ファイルを追加")
        self._add_button.clicked.connect(self._browse_files)
        self._remove_button = QPushButton("選択を削除")
        self._remove_button.clicked.connect(self._remove_selected)
        self._clear_button = QPushButton("すべてクリア")
        self._clear_button.clicked.connect(self._clear_files)
        buttons.addWidget(self._add_button)
        buttons.addWidget(self._remove_button)
        buttons.addWidget(self._clear_button)
        buttons.addStretch(1)
        hint = QLabel("行をダブルクリックすると出力ファイルを開きます")
        hint.setObjectName("hint")
        buttons.addWidget(hint)
        layout.addLayout(buttons)

        return panel

    def _build_log_panel(self) -> QWidget:
        panel = QGroupBox("ログ")
        layout = QVBoxLayout(panel)
        self._log = QPlainTextEdit()
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        layout.addWidget(self._log)
        return panel

    def _build_model_panel(self) -> QWidget:
        panel = QGroupBox("モデルと表示")
        grid = QGridLayout(panel)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("モデル"), 0, 0)
        # 編集可能にすると文字部分のクリックがカーソル移動になり、
        # 言語・テーマと違ってドロップダウンが開かない。モデル ID の直接入力は
        # 末尾の「その他」項目から行う。
        self._model_combo = QComboBox()
        self._model_combo.setToolTip(
            "一覧から選ぶか、「その他」で Hugging Face のモデル ID を直接指定できます"
        )
        for choice in MODELS:
            self._model_combo.addItem(choice.label, choice.model_id)
        self._model_combo.addItem("その他（モデル ID を直接入力）...", _CUSTOM_MODEL)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        grid.addWidget(self._model_combo, 0, 1, 1, 3)

        grid.addWidget(QLabel("言語"), 1, 0)
        self._language_combo = QComboBox()
        for label, code in LANGUAGES:
            self._language_combo.addItem(label, code)
        grid.addWidget(self._language_combo, 1, 1)

        grid.addWidget(QLabel("テーマ"), 1, 2)
        self._theme_combo = QComboBox()
        for label, value in styles.THEME_LABELS:
            self._theme_combo.addItem(label, value)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        grid.addWidget(self._theme_combo, 1, 3)

        self._model_note = QLabel("")
        self._model_note.setObjectName("hint")
        self._model_note.setWordWrap(True)
        grid.addWidget(self._model_note, 2, 0, 1, 4)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        return panel

    def _build_diarization_panel(self) -> QWidget:
        panel = QGroupBox("話者分離")
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        available = diarization_available()
        self._diarize_check = QCheckBox("話者分離を行う")
        self._diarize_check.setEnabled(available)
        self._diarize_check.toggled.connect(self._sync_controls)
        if not available:
            self._diarize_check.setToolTip(
                "pyannote.audio が入っていません。setup.bat を実行し直してください。"
            )
        layout.addWidget(self._diarize_check)

        speakers = QHBoxLayout()
        speakers.addWidget(QLabel("話者数"))
        self._speaker_spin = QSpinBox()
        self._speaker_spin.setRange(0, 20)
        self._speaker_spin.setSpecialValueText("自動推定")
        self._speaker_spin.setToolTip("0 なら話者数を自動で推定します")
        speakers.addWidget(self._speaker_spin)
        speakers.addStretch(1)
        layout.addLayout(speakers)

        note = QLabel(
            "Hugging Face のトークンと\n利用条件への同意が必要です"
            if available
            else "利用できません"
        )
        note.setObjectName("hint")
        layout.addWidget(note)
        layout.addStretch(1)

        return panel

    def _build_output_panel(self) -> QWidget:
        panel = QGroupBox("出力設定")
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        formats = QGridLayout()
        formats.setHorizontalSpacing(16)
        for index, (attribute, label, suffix) in enumerate(OUTPUT_FORMATS):
            check = QCheckBox(f"{label}（<名前>{suffix}）")
            check.toggled.connect(self._sync_controls)
            self._format_checks[attribute] = check
            formats.addWidget(check, index // 2, index % 2)
        layout.addLayout(formats)

        destination = QHBoxLayout()
        self._same_folder_check = QCheckBox("入力ファイルと同じフォルダへ出力")
        self._same_folder_check.toggled.connect(self._sync_controls)
        self._output_edit = QLineEdit()
        self._output_edit.setReadOnly(True)
        self._output_edit.setPlaceholderText("出力先フォルダを選択")
        self._output_button = QPushButton("参照...")
        self._output_button.clicked.connect(self._browse_output_dir)
        destination.addWidget(self._same_folder_check)
        destination.addWidget(self._output_edit, 1)
        destination.addWidget(self._output_button)
        layout.addLayout(destination)

        return panel

    def _build_run_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self._overall_progress = QProgressBar()
        self._overall_progress.setRange(0, 100)
        self._overall_progress.setValue(0)
        self._overall_progress.setFormat("%p%")

        self._start_button = QPushButton("文字起こしを開始")
        self._start_button.setObjectName("primary")
        self._start_button.clicked.connect(self._start)

        self._cancel_button = QPushButton("中止")
        self._cancel_button.clicked.connect(self._cancel)
        self._cancel_button.setEnabled(False)

        bar.addWidget(self._overall_progress, 1)
        bar.addWidget(self._cancel_button)
        bar.addWidget(self._start_button)
        return bar

    # ---------------------------------------------------------------- テーマ

    @staticmethod
    def _system_is_dark() -> bool:
        hints = QGuiApplication.styleHints()
        scheme = getattr(hints, "colorScheme", None)
        if scheme is None:
            return False
        try:
            return scheme() == Qt.ColorScheme.Dark
        except Exception:
            return False

    def _apply_theme(self) -> None:
        self._palette = styles.palette_for(self._theme, self._system_is_dark())
        app = QApplication.instance()
        if app is not None:
            app.setPalette(styles.qt_palette(self._palette))
            app.setStyleSheet(styles.stylesheet(self._palette))
        self._drop_area.set_palette(self._palette)
        self._refresh_table()

    def _status_color(self, status: str) -> str:
        return {
            _STATUS_WAITING: self._palette.text_muted,
            _STATUS_RUNNING: self._palette.accent,
            _STATUS_DONE: self._palette.success,
            _STATUS_ERROR: self._palette.danger,
        }.get(status, self._palette.text)

    @Slot(int)
    def _on_theme_changed(self, _index: int) -> None:
        self._theme = self._theme_combo.currentData() or styles.THEME_SYSTEM
        self._apply_theme()

    @Slot()
    def _on_system_scheme_changed(self, *_args) -> None:
        if self._theme == styles.THEME_SYSTEM:
            self._apply_theme()

    @Slot(int)
    def _on_model_changed(self, _index: int = -1) -> None:
        if self._model_combo.currentData() == _CUSTOM_MODEL:
            self._ask_custom_model()
            return
        self._model_index = self._model_combo.currentIndex()
        self._update_model_note()

    def _update_model_note(self) -> None:
        choice = model_for(self._current_model_id())
        self._model_note.setText(
            f"{choice.note}　|　chunk {choice.chunk_length_s:.0f}s / batch {choice.batch_size}"
        )

    def _ask_custom_model(self) -> None:
        """「その他」を選んだときにモデル ID を尋ねる。"""
        model_id, accepted = QInputDialog.getText(
            self,
            APP_NAME,
            "Hugging Face のモデル ID を入力してください。\n"
            "（例: openai/whisper-large-v3-turbo）",
        )
        model_id = model_id.strip() if accepted else ""
        if not model_id:
            # 取り消されたら直前の選択に戻す。
            self._select_model_index(self._model_index)
            return
        self._select_model(model_id)

    def _select_model(self, model_id: str) -> None:
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

    # --------------------------------------------------------------- 一覧操作

    @Slot(list)
    def _add_paths(self, paths: list[str]) -> None:
        found = collect_media_files(paths, MEDIA_EXTENSIONS)
        if not found:
            self._append_log("対応する音声・動画ファイルが見つかりませんでした。")
            return

        known = {item.path for item in self._items}
        added = 0
        for path in found:
            resolved = path.resolve()
            if resolved in known:
                continue
            known.add(resolved)
            self._items.append(FileItem(path=resolved, duration=probe_duration(resolved)))
            added += 1

        if added:
            self._refresh_table()
            self._append_log(f"{added} 件のファイルを追加しました。")
        self._sync_controls()

    @Slot()
    def _browse_files(self) -> None:
        start_dir = self._settings.value("last_input_dir", "", type=str)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "音声・動画ファイルを選択", start_dir, FILE_DIALOG_FILTER
        )
        if paths:
            self._settings.setValue("last_input_dir", str(Path(paths[0]).parent))
            self._add_paths(paths)

    @Slot()
    def _remove_selected(self) -> None:
        rows = sorted({index.row() for index in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self._items):
                del self._items[row]
        self._refresh_table()
        self._sync_controls()

    @Slot()
    def _clear_files(self) -> None:
        self._items.clear()
        self._refresh_table()
        self._sync_controls()

    def _refresh_table(self) -> None:
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self._set_cell(row, _COL_NAME, item.path.name, tooltip=str(item.path))
            duration = format_timestamp(item.duration) if item.duration else "-"
            self._set_cell(row, _COL_DURATION, duration, align=Qt.AlignCenter)
            self._set_cell(
                row,
                _COL_STATUS,
                item.status,
                align=Qt.AlignCenter,
                color=self._status_color(item.status),
                tooltip=item.error or None,
            )
            self._set_cell(
                row, _COL_PROGRESS, f"{item.progress * 100:.0f}%", align=Qt.AlignCenter
            )
        self._update_overall_progress()

    def _set_cell(
        self,
        row: int,
        column: int,
        text: str,
        *,
        align=Qt.AlignVCenter | Qt.AlignLeft,
        color: str | None = None,
        tooltip: str | None = None,
    ) -> None:
        cell = self._table.item(row, column)
        if cell is None:
            cell = QTableWidgetItem()
            self._table.setItem(row, column, cell)
        cell.setText(text)
        cell.setTextAlignment(align)
        cell.setForeground(QColor(color or self._palette.text))
        cell.setToolTip(tooltip or "")

    def _update_overall_progress(self) -> None:
        if not self._items:
            self._overall_progress.setValue(0)
            return
        total = sum(item.progress for item in self._items) / len(self._items)
        self._overall_progress.setValue(int(total * 100))

    @Slot(QTableWidgetItem)
    def _open_result(self, cell: QTableWidgetItem) -> None:
        row = cell.row()
        if not (0 <= row < len(self._items)):
            return
        item = self._items[row]
        target = item.outputs[0] if item.outputs else str(item.path.parent)
        try:
            os.startfile(target)  # noqa: S606 - Windows 専用アプリ
        except OSError as exc:
            self._append_log(f"[エラー] 開けませんでした: {exc}")

    # ----------------------------------------------------------------- 設定

    @Slot()
    def _browse_output_dir(self) -> None:
        current = self._output_edit.text() or self._settings.value(
            "last_input_dir", "", type=str
        )
        directory = QFileDialog.getExistingDirectory(self, "出力先フォルダを選択", current)
        if directory:
            self._set_output_dir(directory)
            self._same_folder_check.setChecked(False)
            self._sync_controls()

    def _set_output_dir(self, directory: str) -> None:
        self._output_edit.setText(directory)
        # 長いパスでも先頭から見えるようにする。
        self._output_edit.setCursorPosition(0)
        self._output_edit.setToolTip(directory)

    def _current_model_id(self) -> str:
        data = self._model_combo.currentData()
        if not data or data == _CUSTOM_MODEL:
            return DEFAULT_MODEL_ID
        return str(data)

    def _current_options(self) -> OutputOptions:
        output_dir = None
        if not self._same_folder_check.isChecked() and self._output_edit.text():
            output_dir = Path(self._output_edit.text())
        options = OutputOptions(output_dir=output_dir)
        for attribute, check in self._format_checks.items():
            setattr(options, attribute, check.isChecked())
        return options

    def _current_diarization(self) -> DiarizationOptions:
        return DiarizationOptions(
            enabled=self._diarize_check.isChecked() and self._diarize_check.isEnabled(),
            num_speakers=self._speaker_spin.value(),
        )

    def _sync_controls(self) -> None:
        running = self._thread is not None
        use_same_folder = self._same_folder_check.isChecked()

        self._output_edit.setEnabled(not use_same_folder and not running)
        self._output_button.setEnabled(not use_same_folder and not running)
        self._speaker_spin.setEnabled(
            self._diarize_check.isChecked() and self._diarize_check.isEnabled() and not running
        )

        editable = [
            self._drop_area,
            self._add_button,
            self._remove_button,
            self._clear_button,
            self._same_folder_check,
            self._model_combo,
            self._language_combo,
        ]
        editable.extend(self._format_checks.values())
        for widget in editable:
            widget.setEnabled(not running)
        if diarization_available():
            self._diarize_check.setEnabled(not running)

        ready = bool(self._items) and self._current_options().any_selected
        self._start_button.setEnabled(ready and not running)
        self._cancel_button.setEnabled(running)

        if running:
            return
        if not self._items:
            self.statusBar().showMessage("ファイルを追加してください")
        elif not self._current_options().any_selected:
            self.statusBar().showMessage("出力形式を 1 つ以上選んでください")
        else:
            self.statusBar().showMessage(f"{len(self._items)} 件のファイルを処理できます")

    def _restore_settings(self) -> None:
        settings = self._settings

        self._select_model(settings.value("model_id", DEFAULT_MODEL_ID, type=str))

        language = settings.value("language", "ja", type=str) or None
        language_index = self._language_combo.findData(language)
        self._language_combo.setCurrentIndex(max(0, language_index))

        self._theme = settings.value("theme", styles.THEME_SYSTEM, type=str)
        theme_index = self._theme_combo.findData(self._theme)
        self._theme_combo.setCurrentIndex(max(0, theme_index))

        self._diarize_check.setChecked(
            settings.value("diarize", False, type=bool) and diarization_available()
        )
        self._speaker_spin.setValue(settings.value("num_speakers", 0, type=int))

        defaults = {"plain_text": True, "timestamped": True}
        for attribute, check in self._format_checks.items():
            check.setChecked(
                settings.value(f"format_{attribute}", defaults.get(attribute, False), type=bool)
            )

        self._same_folder_check.setChecked(settings.value("same_folder", True, type=bool))
        self._set_output_dir(settings.value("output_dir", "", type=str))

    def _save_settings(self) -> None:
        settings = self._settings
        settings.setValue("model_id", self._current_model_id())
        settings.setValue("language", self._language_combo.currentData() or "")
        settings.setValue("theme", self._theme)
        settings.setValue("diarize", self._diarize_check.isChecked())
        settings.setValue("num_speakers", self._speaker_spin.value())
        for attribute, check in self._format_checks.items():
            settings.setValue(f"format_{attribute}", check.isChecked())
        settings.setValue("same_folder", self._same_folder_check.isChecked())
        settings.setValue("output_dir", self._output_edit.text())

    # ----------------------------------------------------------------- 実行

    @Slot()
    def _start(self) -> None:
        if self._thread is not None:
            return

        options = self._current_options()
        if options.output_dir is not None and not options.output_dir.exists():
            QMessageBox.warning(self, APP_NAME, "出力先フォルダが見つかりません。")
            return

        for item in self._items:
            item.status = _STATUS_WAITING
            item.progress = 0.0
            item.outputs = []
            item.error = ""
        self._refresh_table()

        worker = TranscribeWorker(
            [item.path for item in self._items],
            options,
            self._current_diarization(),
            self._current_model_id(),
            self._language_combo.currentData(),
            self._transcriber,
            self._diarizer,
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.diarization_disabled.connect(self._on_diarization_disabled)
        worker.file_started.connect(self._on_file_started)
        worker.file_progress.connect(self._on_file_progress)
        worker.file_finished.connect(self._on_file_finished)
        worker.file_failed.connect(self._on_file_failed)
        worker.finished.connect(self._on_all_finished)

        self._worker = worker
        self._thread = thread
        self._sync_controls()
        self.statusBar().showMessage("処理中...")
        self._append_log("---- 文字起こしを開始します ----")
        thread.start()

    @Slot()
    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._cancel_button.setEnabled(False)
            self.statusBar().showMessage("中断しています（現在の区間の処理が終わるまで待ちます）")
            self._append_log("中断を要求しました。")

    @Slot(str)
    def _on_diarization_disabled(self, reason: str) -> None:
        """有効にした話者分離が実行できなかったことを、ログだけでなく画面でも知らせる。

        出力に話者ラベルが付かないまま「完了」になると、成功したと誤解されるため。
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(APP_NAME)
        box.setText("話者分離を実行できないため、文字起こしのみ続行します。")
        box.setInformativeText("出力に話者ラベル（話者1・話者2 …）は付きません。")
        box.setDetailedText(reason)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    @Slot(int)
    def _on_file_started(self, index: int) -> None:
        if 0 <= index < len(self._items):
            self._items[index].status = _STATUS_RUNNING
            self._refresh_table()
            self._table.scrollToItem(self._table.item(index, _COL_NAME))

    @Slot(int, float)
    def _on_file_progress(self, index: int, ratio: float) -> None:
        if 0 <= index < len(self._items):
            self._items[index].progress = max(0.0, min(1.0, ratio))
            self._set_cell(
                index,
                _COL_PROGRESS,
                f"{self._items[index].progress * 100:.0f}%",
                align=Qt.AlignCenter,
            )
            self._update_overall_progress()

    @Slot(int, list)
    def _on_file_finished(self, index: int, outputs: list) -> None:
        if 0 <= index < len(self._items):
            item = self._items[index]
            item.status = _STATUS_DONE
            item.progress = 1.0
            item.outputs = [str(path) for path in outputs]
            self._refresh_table()

    @Slot(int, str)
    def _on_file_failed(self, index: int, message: str) -> None:
        if 0 <= index < len(self._items):
            self._items[index].status = _STATUS_ERROR
            self._items[index].error = message
            self._refresh_table()

    @Slot(bool)
    def _on_all_finished(self, cancelled: bool) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = None
        self._worker = None

        done = sum(1 for item in self._items if item.status == _STATUS_DONE)
        failed = sum(1 for item in self._items if item.status == _STATUS_ERROR)
        summary = f"完了 {done} 件 / エラー {failed} 件"
        if cancelled:
            summary = "中断しました（" + summary + "）"
        self._append_log(f"---- {summary} ----")
        self.statusBar().showMessage(summary)
        self._sync_controls()

    # ----------------------------------------------------------------- 雑務

    @Slot(str)
    def _append_log(self, message: str) -> None:
        stamp = QTime.currentTime().toString("HH:mm:ss")
        self._log.appendPlainText(f"{stamp}  {message}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None:
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "処理中です。中断して終了しますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            if self._worker is not None:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait(30_000)

        self._save_settings()
        super().closeEvent(event)
