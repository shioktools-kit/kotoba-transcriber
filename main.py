"""Kotoba Transcriber のエントリポイント。"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# パッケージの import 時に PySide6 向けの DLL 対策が走るので、
# PySide6 より先にこちらを読むこと（kotoba_transcriber/qtfix.py 参照）。
import kotoba_transcriber  # noqa: F401

from PySide6.QtWidgets import QApplication

from kotoba_transcriber.config import APP_NAME, ORG_NAME
from kotoba_transcriber.ui.main_window import MainWindow

# pythonw.exe で起動するとコンソールがないので、落ちた理由をここに残す。
ERROR_LOG = Path(os.environ.get("LOCALAPPDATA", ".")) / "KotobaTranscriber" / "error.log"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")

    # 配色は MainWindow がテーマ設定に合わせて適用する（styles.stylesheet /
    # styles.qt_palette）。ここでスタイルシートを触らないこと。
    window = MainWindow()
    window.show()
    return app.exec()


def _report_crash(error: BaseException) -> None:
    """コンソールがなくても原因が分かるようにする。"""
    detail = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        ERROR_LOG.write_text(detail, encoding="utf-8")
        location = str(ERROR_LOG)
    except OSError:
        location = "（ログを書き出せませんでした）"

    sys.stderr.write(detail)
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"{APP_NAME} の起動に失敗しました。\n\n{error}\n\n詳細: {location}",
            APP_NAME,
            0x10,  # MB_ICONERROR
        )
    except Exception:
        pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - 起動失敗をユーザーに見せる
        _report_crash(exc)
        sys.exit(1)
