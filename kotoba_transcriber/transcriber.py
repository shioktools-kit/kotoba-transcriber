"""transformers の ASR pipeline によるローカル文字起こし。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .audio import split_spans
from .compat import disable_broken_torchcodec
from .config import DEFAULT_MODEL_ID, TARGET_SR, model_for

LogFn = Callable[[str], None]
ProgressFn = Callable[[float], None]
CancelFn = Callable[[], bool]


@dataclass(frozen=True)
class Segment:
    """発話ひとかたまり。時刻は入力ファイル先頭からの秒数。"""

    start: float
    end: float
    text: str
    speaker: str | None = None


class Cancelled(Exception):
    """ユーザーが処理を中断した。"""


class Transcriber:
    """モデルを保持して使い回す。設定が変わったときだけ読み込み直す。"""

    def __init__(self) -> None:
        self._pipe = None
        self._loaded_key: tuple[str, str | None] | None = None
        self._language: str | None = "ja"
        self.device_label = "未初期化"

    @property
    def is_loaded(self) -> bool:
        return self._pipe is not None

    def load(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        language: str | None = "ja",
        log: LogFn | None = None,
    ) -> None:
        key = (model_id, language)
        if self._pipe is not None and self._loaded_key == key:
            return
        if self._pipe is not None:
            self.unload()

        import torch
        from transformers import pipeline

        # transformers が壊れた torchcodec を掴まないようにする（compat.py 参照）。
        disable_broken_torchcodec(log)

        choice = model_for(model_id)

        if torch.cuda.is_available():
            device = "cuda:0"
            dtype = torch.float16
            self.device_label = f"CUDA ({torch.cuda.get_device_name(0)})"
        else:
            device = "cpu"
            dtype = torch.float32
            self.device_label = "CPU"

        if log:
            log(f"デバイス: {self.device_label}")
            log(f"モデルを読み込んでいます: {model_id}")
            log("初回はモデルのダウンロードが走ります。しばらくお待ちください。")

        kwargs = dict(
            task="automatic-speech-recognition",
            model=model_id,
            dtype=dtype,
            device=device,
            chunk_length_s=choice.chunk_length_s,
            batch_size=choice.batch_size,
        )
        try:
            self._pipe = pipeline(
                **kwargs, model_kwargs={"attn_implementation": "sdpa"}
            )
        except Exception as exc:  # sdpa 非対応環境では既定の attention へ落とす
            if log:
                log(f"sdpa を使えないため既定の attention を使います ({exc})")
            self._pipe = pipeline(**kwargs)

        self._loaded_key = key
        self._language = language
        if log:
            log("モデルの読み込みが完了しました。")

    def unload(self) -> None:
        self._pipe = None
        self._loaded_key = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def transcribe(
        self,
        waveform: np.ndarray,
        sample_rate: int = TARGET_SR,
        progress: ProgressFn | None = None,
        should_cancel: CancelFn | None = None,
    ) -> list[Segment]:
        if self._pipe is None:
            raise RuntimeError("モデルが読み込まれていません")

        generate_kwargs: dict[str, object] = {"task": "transcribe"}
        if self._language:
            generate_kwargs["language"] = self._language

        spans = split_spans(waveform, sample_rate)
        total = max(1, int(waveform.size))
        segments: list[Segment] = []

        for start, end in spans:
            if should_cancel and should_cancel():
                raise Cancelled
            chunk = waveform[start:end]
            result = self._pipe(
                {"array": chunk, "sampling_rate": sample_rate},
                return_timestamps=True,
                generate_kwargs=generate_kwargs,
            )
            segments.extend(
                _to_segments(result, start / sample_rate, chunk.size / sample_rate)
            )
            if progress:
                progress(end / total)

        return segments


def _to_segments(result: dict, offset: float, duration: float) -> list[Segment]:
    chunks = result.get("chunks") or []
    if not chunks:
        text = (result.get("text") or "").strip()
        return [Segment(offset, offset + duration, text)] if text else []

    segments: list[Segment] = []
    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        stamp = chunk.get("timestamp") or (None, None)
        start = float(stamp[0]) if stamp[0] is not None else 0.0
        end = float(stamp[1]) if stamp[1] is not None else duration
        segments.append(Segment(offset + start, offset + end, text))
    return segments
