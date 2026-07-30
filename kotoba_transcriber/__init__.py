"""kotoba-whisper をローカルで動かす文字起こしアプリ。"""

import os

# Windows でシンボリックリンクが作れない環境の警告を抑える。
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from .qtfix import prepare_qt_dll_search

# PySide6 を使うモジュールより先に必ず走らせる。
prepare_qt_dll_search()

__all__ = ["prepare_qt_dll_search"]
