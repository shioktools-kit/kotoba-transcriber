"""メインウィンドウ。ヘッダー＋（メイン画面 / 設定画面）のカード 1 枚で構成する。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTime, Slot
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..audio import collect_media_files, probe_duration
from ..config import (
    APP_NAME,
    FILE_DIALOG_FILTER,
    MEDIA_EXTENSIONS,
    ORG_NAME,
    OUTPUT_FORMATS,
    DEFAULT_MODEL_ID,
    DiarizationOptions,
)
from ..diarization import Diarizer
from ..transcriber import Transcriber
from ..worker import TranscribeWorker
from . import styles
from .main_page import MainPage
from .settings_page import SettingsPage
from .widgets import HeaderBar, apply_drop_shadow

_STATUS_WAITING = "待機"
_STATUS_RUNNING = "処理中"
_STATUS_DONE = "完了"
_STATUS_ERROR = "エラー"

_PAGE_MAIN = 0
_PAGE_SETTINGS = 1


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
        self.resize(1080, 760)
        # メインページ・設定ページとも中身は QScrollArea に収めてあるので、
        # ウィンドウを縮めたときはレイアウトが壊れる代わりにスクロールバーが
        # 出るだけになる。ここでの最小サイズはヘッダーとタイトルバーが
        # 見苦しくならない程度の控えめな下限でよい。
        self.setMinimumSize(760, 560)

        self._items: list[FileItem] = []
        self._transcriber = Transcriber()
        self._diarizer = Diarizer()
        self._thread: QThread | None = None
        self._worker: TranscribeWorker | None = None
        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._theme = styles.THEME_SYSTEM
        self._palette = styles.LIGHT

        self._build_ui()
        self._restore_settings()
        self._apply_theme()
        self._sync_controls()

        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        canvas = QWidget()
        canvas.setObjectName("canvas")
        canvas.setAttribute(Qt.WA_StyledBackground, True)
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(28, 28, 28, 28)

        self._card = QWidget()
        self._card.setObjectName("card")
        self._card.setAttribute(Qt.WA_StyledBackground, True)
        # 幅の上限は設けない。キャンバスの余白（28px）分だけ残して、
        # フルスクリーン時も画面をいっぱいに使う。
        # 横方向は「余白があるだけ伸びたい」ポリシーを明示する。既定の
        # Preferred のままだと、中身（QStackedWidget 経由の QScrollArea）
        # の sizeHint に留まってしまい、ウィンドウを広げても伸びてくれない。
        self._card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._header = HeaderBar(self._palette)
        self._header.gearClicked.connect(lambda: self._go_to(_PAGE_SETTINGS))
        self._header.backClicked.connect(lambda: self._go_to(_PAGE_MAIN))
        card_layout.addWidget(self._header)

        self._stack = QStackedWidget()

        self._main_page = MainPage()
        self._main_page.filesDropped.connect(self._add_paths)
        self._main_page.dropAreaClicked.connect(self._browse_files)
        self._main_page.addClicked.connect(self._browse_files)
        self._main_page.removeSelectedClicked.connect(self._remove_selected)
        self._main_page.clearClicked.connect(self._clear_files)
        self._main_page.rowDoubleClicked.connect(self._open_result)
        self._main_page.startClicked.connect(self._start)
        self._main_page.cancelClicked.connect(self._cancel)

        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QScrollArea.NoFrame)
        main_wrap = QWidget()
        main_wrap_layout = QVBoxLayout(main_wrap)
        main_wrap_layout.setContentsMargins(24, 24, 24, 30)
        main_wrap_layout.addWidget(self._main_page)
        main_scroll.setWidget(main_wrap)
        self._stack.addWidget(main_scroll)

        self._settings_page = SettingsPage()
        self._settings_page.themeChanged.connect(self._on_theme_changed)
        self._settings_page.changed.connect(self._sync_controls)

        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QScrollArea.NoFrame)
        settings_inner = QWidget()
        settings_inner_layout = QVBoxLayout(settings_inner)
        settings_inner_layout.setContentsMargins(24, 24, 24, 30)
        settings_inner_layout.addWidget(self._settings_page)
        settings_scroll.setWidget(settings_inner)
        self._stack.addWidget(settings_scroll)

        card_layout.addWidget(self._stack, 1)
        canvas_layout.addWidget(self._card)

        self.setCentralWidget(canvas)
        self.statusBar().showMessage("ファイルを追加してください")

    def _go_to(self, page: int) -> None:
        self._stack.setCurrentIndex(page)
        self._header.set_mode(is_settings=(page == _PAGE_SETTINGS))

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
        apply_drop_shadow(self._card, self._palette)
        self._header.set_palette(self._palette)
        self._main_page.set_palette(self._palette)
        self._settings_page.set_palette(self._palette)
        self._refresh_files()

    @Slot(str)
    def _on_theme_changed(self, value: str) -> None:
        self._theme = value or styles.THEME_SYSTEM
        self._apply_theme()

    @Slot()
    def _on_system_scheme_changed(self, *_args) -> None:
        if self._theme == styles.THEME_SYSTEM:
            self._apply_theme()

    # --------------------------------------------------------------- 一覧操作

    def _refresh_files(self) -> None:
        self._main_page.file_list.set_items(self._items)
        self._update_overall_progress()

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
            self._refresh_files()
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
        rows = sorted(self._main_page.file_list.selected_indices(), reverse=True)
        for row in rows:
            if 0 <= row < len(self._items):
                del self._items[row]
        self._main_page.file_list.clear_selection()
        self._refresh_files()
        self._sync_controls()

    @Slot()
    def _clear_files(self) -> None:
        self._items.clear()
        self._refresh_files()
        self._sync_controls()

    def _update_overall_progress(self) -> None:
        if not self._items:
            self._main_page.set_progress(0)
            return
        total = sum(item.progress for item in self._items) / len(self._items)
        self._main_page.set_progress(int(total * 100))

    @Slot(int)
    def _open_result(self, index: int) -> None:
        if not (0 <= index < len(self._items)):
            return
        item = self._items[index]
        target = item.outputs[0] if item.outputs else str(item.path.parent)
        try:
            os.startfile(target)  # noqa: S606 - Windows 専用アプリ
        except OSError as exc:
            self._append_log(f"[エラー] 開けませんでした: {exc}")

    # ----------------------------------------------------------------- 設定

    def _sync_controls(self) -> None:
        running = self._thread is not None

        self._main_page.drop_area.setEnabled(not running)
        self._main_page.file_list.set_controls_enabled(not running)
        self._main_page.language_combo.setEnabled(not running)
        self._settings_page.set_enabled_all(not running)

        options = self._settings_page.current_options()
        ready = bool(self._items) and options.any_selected
        self._main_page.start_button.setEnabled(ready and not running)
        self._main_page.cancel_button.setEnabled(running)

        if running:
            return
        if not self._items:
            self.statusBar().showMessage("ファイルを追加してください")
        elif not options.any_selected:
            self.statusBar().showMessage("出力形式を 1 つ以上選んでください")
        else:
            self.statusBar().showMessage(f"{len(self._items)} 件のファイルを処理できます")

    def _restore_settings(self) -> None:
        settings = self._settings

        self._settings_page.select_model(settings.value("model_id", DEFAULT_MODEL_ID, type=str))

        language = settings.value("language", "ja", type=str) or None
        language_index = self._main_page.language_combo.findData(language)
        self._main_page.language_combo.setCurrentIndex(max(0, language_index))

        self._theme = settings.value("theme", styles.THEME_SYSTEM, type=str)
        self._settings_page.set_theme(self._theme)

        self._settings_page.set_diarization(
            settings.value("diarize", False, type=bool),
            settings.value("num_speakers", 0, type=int),
        )

        defaults = {"plain_text": True, "timestamped": True}
        formats = {
            attribute: settings.value(f"format_{attribute}", defaults.get(attribute, False), type=bool)
            for attribute, _label, _suffix in OUTPUT_FORMATS
        }
        self._settings_page.set_output_formats(formats)

        self._settings_page.set_same_folder(settings.value("same_folder", True, type=bool))
        self._settings_page.set_output_dir(settings.value("output_dir", "", type=str))

    def _save_settings(self) -> None:
        settings = self._settings
        settings.setValue("model_id", self._settings_page.current_model_id())
        settings.setValue("language", self._main_page.language_combo.currentData() or "")
        settings.setValue("theme", self._theme)
        settings.setValue("diarize", self._settings_page.diarization_enabled())
        settings.setValue("num_speakers", self._settings_page.num_speakers())
        options = self._settings_page.current_options()
        for attribute, _label, _suffix in OUTPUT_FORMATS:
            settings.setValue(f"format_{attribute}", getattr(options, attribute))
        settings.setValue("same_folder", self._settings_page.same_folder())
        settings.setValue("output_dir", self._settings_page.output_dir_text())

    # ----------------------------------------------------------------- 実行

    @Slot()
    def _start(self) -> None:
        if self._thread is not None:
            return

        options = self._settings_page.current_options()
        if options.output_dir is not None and not options.output_dir.exists():
            QMessageBox.warning(self, APP_NAME, "出力先フォルダが見つかりません。")
            return

        for item in self._items:
            item.status = _STATUS_WAITING
            item.progress = 0.0
            item.outputs = []
            item.error = ""
        self._refresh_files()

        worker = TranscribeWorker(
            [item.path for item in self._items],
            options,
            DiarizationOptions(
                enabled=self._settings_page.diarization_enabled(),
                num_speakers=self._settings_page.num_speakers(),
            ),
            self._settings_page.current_model_id(),
            self._main_page.language_combo.currentData(),
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
            self._main_page.cancel_button.setEnabled(False)
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
            self._main_page.file_list.update_row(index, self._items[index])
            self._main_page.file_list.scroll_to(index)

    @Slot(int, float)
    def _on_file_progress(self, index: int, ratio: float) -> None:
        if 0 <= index < len(self._items):
            self._items[index].progress = max(0.0, min(1.0, ratio))
            self._main_page.file_list.update_row(index, self._items[index])
            self._update_overall_progress()

    @Slot(int, list)
    def _on_file_finished(self, index: int, outputs: list) -> None:
        if 0 <= index < len(self._items):
            item = self._items[index]
            item.status = _STATUS_DONE
            item.progress = 1.0
            item.outputs = [str(path) for path in outputs]
            self._main_page.file_list.update_row(index, item)
            self._update_overall_progress()

    @Slot(int, str)
    def _on_file_failed(self, index: int, message: str) -> None:
        if 0 <= index < len(self._items):
            self._items[index].status = _STATUS_ERROR
            self._items[index].error = message
            self._main_page.file_list.update_row(index, self._items[index])

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
        self._main_page.append_log(f"{stamp}  {message}")

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
