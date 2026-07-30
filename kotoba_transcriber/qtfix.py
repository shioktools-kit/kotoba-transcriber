"""PySide6 を import する前に必要な DLL 検索まわりの下ごしらえ。

`kotoba_transcriber` パッケージの読み込み時に一度だけ実行されるので、
PySide6 を使うモジュールはこのパッケージ経由で import すれば安全になる。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_done = False


def prepare_qt_dll_search() -> None:
    """PySide6 が別ライブラリの DLL を掴んで落ちるのを防ぐ。

    Anaconda 由来の Python で作った venv では `<anaconda>\\Library\\bin` が
    常に DLL 検索対象に入る。そこにある ICU 73 は関数名が `ucnv_open_73` の
    ようにサフィックス付きなので、`ucnv_open` を要求する Qt6Core.dll が
    「DLL load failed ... 指定されたプロシージャが見つかりません」で落ちる。
    conda の Python は `add_dll_directory` で追加するため PATH の掃除では効かない。

    Windows 同梱の ICU を先に読み込んでおくと、以後 `icuuc.dll` の解決は
    ロード済みモジュールに当たるので Anaconda 側が使われなくなる。
    あわせて PATH 上の別ビルドの Qt6 も取り除く。
    """
    global _done
    if _done or sys.platform != "win32":
        _done = True
        return
    _done = True

    import ctypes

    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    for name in ("icu.dll", "icuuc.dll", "icuin.dll"):
        try:
            ctypes.WinDLL(str(system32 / name))
        except OSError:
            pass

    kept = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        try:
            if (Path(entry) / "Qt6Core.dll").exists():
                continue
        except OSError:
            pass
        kept.append(entry)
    os.environ["PATH"] = os.pathsep.join(kept)
