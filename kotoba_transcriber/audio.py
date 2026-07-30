"""音声・動画ファイルを 16kHz モノラルの float32 波形へ変換する。

PyAV を使うので ffmpeg.exe を別途インストールする必要はない。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

import av
import numpy as np

from .config import (
    SEGMENT_SECONDS,
    SPLIT_SEARCH_SECONDS,
    SPLIT_WINDOW_SECONDS,
    TARGET_SR,
)

ProgressFn = Callable[[float], None]


def probe_duration(path: Path) -> float:
    """メディアの長さ（秒）を返す。取得できなければ 0.0。"""
    try:
        with av.open(str(path)) as container:
            stream = _audio_stream(container)
            return _duration_seconds(container, stream)
    except Exception:
        return 0.0


def load_waveform(
    path: Path,
    sample_rate: int = TARGET_SR,
    progress: ProgressFn | None = None,
) -> np.ndarray:
    """メディアをデコードして [-1.0, 1.0] の 1 次元 float32 配列にする。"""
    path = Path(path)
    blocks: list[np.ndarray] = []
    written = 0

    with av.open(str(path)) as container:
        stream = _audio_stream(container)
        if stream is None:
            raise ValueError("音声トラックが見つかりません")
        stream.thread_type = "AUTO"

        duration = _duration_seconds(container, stream)
        expected = int(duration * sample_rate) if duration > 0 else 0
        resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)

        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                block = out.to_ndarray().reshape(-1)
                blocks.append(block)
                written += block.size
            if progress and expected:
                progress(min(1.0, written / expected))

        for out in resampler.resample(None):
            block = out.to_ndarray().reshape(-1)
            blocks.append(block)
            written += block.size

    if not blocks:
        raise ValueError("音声をデコードできませんでした")

    if progress:
        progress(1.0)

    pcm = np.concatenate(blocks)
    return (pcm.astype(np.float32) / 32768.0)


def split_spans(
    waveform: np.ndarray,
    sample_rate: int = TARGET_SR,
    segment_seconds: float = SEGMENT_SECONDS,
    search_seconds: float = SPLIT_SEARCH_SECONDS,
) -> list[tuple[int, int]]:
    """波形を扱いやすい長さに区切る [start, end) のリストを返す。

    区切り位置は目標地点の前後を探索して最も静かなところに寄せる。
    語の途中でぶつ切りにして単語が失われるのを避けるため。
    """
    total = int(waveform.size)
    segment = int(segment_seconds * sample_rate)
    if total <= 0:
        return []
    # 1 区間を少し超える程度なら分割しない。
    if total <= int(segment * 1.2):
        return [(0, total)]

    search = int(search_seconds * sample_rate)
    window = max(1, int(SPLIT_WINDOW_SECONDS * sample_rate))
    margin = sample_rate  # 区間が 1 秒未満にならないようにする

    bounds = [0]
    while total - bounds[-1] > int(segment * 1.2):
        start = bounds[-1]
        target = start + segment
        low = max(start + margin, target - search)
        high = min(total - margin, target + search)
        if high - low > window:
            cut = _quietest_offset(waveform, low, high, window)
        else:
            cut = min(max(target, start + margin), total - margin)
        bounds.append(cut)
    bounds.append(total)

    return list(zip(bounds[:-1], bounds[1:]))


def _quietest_offset(waveform: np.ndarray, low: int, high: int, window: int) -> int:
    """[low, high) の中で最もエネルギーが低い窓の中心位置を返す。"""
    region = waveform[low:high].astype(np.float64)
    cumulative = np.concatenate(([0.0], np.cumsum(region * region)))
    sums = cumulative[window:] - cumulative[:-window]
    return low + int(np.argmin(sums)) + window // 2


def _audio_stream(container: "av.container.InputContainer"):
    return next((s for s in container.streams if s.type == "audio"), None)


def _duration_seconds(container, stream) -> float:
    if stream is not None and stream.duration is not None and stream.time_base:
        return float(stream.duration * stream.time_base)
    if container.duration is not None:
        return float(container.duration) / av.time_base
    return 0.0


def collect_media_files(paths: Sequence[str], extensions: set[str]) -> list[Path]:
    """ドロップされたパスから対応メディアだけを取り出す（フォルダは 1 階層展開）。"""
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_file() and child.suffix.lower() in extensions:
                    found.append(child)
        elif path.is_file() and path.suffix.lower() in extensions:
            found.append(path)
    return found
