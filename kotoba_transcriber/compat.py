"""依存ライブラリ同士の噛み合わせを直すための小細工。"""

from __future__ import annotations

import importlib.util
from typing import Callable

LogFn = Callable[[str], None]

_torchcodec_checked = False


def disable_broken_torchcodec(log: LogFn | None = None) -> bool:
    """読み込めない torchcodec を transformers から隠す。

    torchcodec は FFmpeg の共有ライブラリ (avutil などの DLL) を要求する。
    pyannote.audio が依存として引き込むため入ってはいるが、FFmpeg 本体を
    入れていない環境では DLL のロードに失敗する。

    transformers 4.57 の ASR pipeline は `is_torchcodec_available()`
    （= spec があるかどうかだけの判定）が真だと preprocess の中で無条件に
    `import torchcodec` する。用途は入力が AudioDecoder かどうかの
    isinstance 判定だけなのに、そこで例外が出て文字起こし全体が落ちる。

    こちらは常に numpy 配列を渡すので torchcodec は不要。実際に import して
    みて駄目なら、transformers 側のフラグを False にして経路ごと回避する。

    Returns:
        フラグを倒した（= torchcodec が壊れていた）なら True。
    """
    global _torchcodec_checked
    if _torchcodec_checked:
        return False
    _torchcodec_checked = True

    if importlib.util.find_spec("torchcodec") is None:
        return False

    try:
        import torchcodec.decoders  # noqa: F401
    except Exception as exc:
        try:
            from transformers.utils import import_utils

            import_utils._torchcodec_available = False
        except Exception:
            return False
        if log:
            log(
                "torchcodec を読み込めないため無効化しました"
                f"（音声は PyAV でデコードするので影響ありません）: {type(exc).__name__}"
            )
        return True

    return False
