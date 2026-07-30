"""文字起こし結果をテキスト・字幕・JSON へ整形する。"""

from __future__ import annotations

import json
from typing import Iterable, Sequence

from .transcriber import Segment

_SENTENCE_ENDS = "。！？"


def format_timestamp(seconds: float) -> str:
    """`HH:MM:SS`。一覧表示と本文用。"""
    total = max(0, int(seconds))
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _subtitle_timestamp(seconds: float, separator: str) -> str:
    """SRT / VTT 用の `HH:MM:SS,mmm` 形式。"""
    total = max(0.0, seconds)
    hours, remainder = divmod(int(total), 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int(round((total - int(total)) * 1000))
    if millis == 1000:  # 丸め上がりを繰り上げる
        millis = 0
        secs += 1
        if secs == 60:
            secs = 0
            minutes += 1
            if minutes == 60:
                minutes = 0
                hours += 1
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _with_speaker(segment: Segment) -> str:
    if segment.speaker:
        return f"{segment.speaker}: {segment.text}"
    return segment.text


def to_plain_text(segments: Sequence[Segment]) -> str:
    """タイムスタンプなしの本文。

    話者分離ありなら話者ごとに段落を分け、なしなら文末で改行する。
    """
    if any(segment.speaker for segment in segments):
        lines = [
            f"{speaker}: {''.join(s.text for s in group)}"
            for speaker, group in _group_by_speaker(segments)
        ]
        return "\n\n".join(lines) + "\n"

    body = "".join(segment.text for segment in segments)
    for mark in _SENTENCE_ENDS:
        body = body.replace(mark, mark + "\n")
    lines = [line.strip() for line in body.splitlines()]
    return "\n".join(line for line in lines if line) + "\n"


def to_timestamped_text(segments: Sequence[Segment]) -> str:
    """`[00:01:23] 話者1: 発言内容` の形式。"""
    lines = [
        f"[{format_timestamp(segment.start)}] {_with_speaker(segment)}"
        for segment in segments
        if segment.text
    ]
    return "\n".join(lines) + "\n"


def to_srt(segments: Sequence[Segment]) -> str:
    blocks = []
    index = 0
    for segment in segments:
        if not segment.text:
            continue
        index += 1
        start = _subtitle_timestamp(segment.start, ",")
        end = _subtitle_timestamp(max(segment.end, segment.start + 0.1), ",")
        blocks.append(f"{index}\n{start} --> {end}\n{_with_speaker(segment)}\n")
    return "\n".join(blocks)


def to_vtt(segments: Sequence[Segment]) -> str:
    blocks = ["WEBVTT\n"]
    for segment in segments:
        if not segment.text:
            continue
        start = _subtitle_timestamp(segment.start, ".")
        end = _subtitle_timestamp(max(segment.end, segment.start + 0.1), ".")
        blocks.append(f"{start} --> {end}\n{_with_speaker(segment)}\n")
    return "\n".join(blocks)


def to_json(segments: Sequence[Segment], source: str = "", model: str = "") -> str:
    payload = {
        "source": source,
        "model": model,
        "text": "".join(segment.text for segment in segments),
        "segments": [
            {
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": segment.text,
                "speaker": segment.speaker,
            }
            for segment in segments
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _group_by_speaker(
    segments: Iterable[Segment],
) -> list[tuple[str, list[Segment]]]:
    """連続する同じ話者の発話をまとめる。"""
    groups: list[tuple[str, list[Segment]]] = []
    for segment in segments:
        if not segment.text:
            continue
        speaker = segment.speaker or "話者不明"
        if groups and groups[-1][0] == speaker:
            groups[-1][1].append(segment)
        else:
            groups.append((speaker, [segment]))
    return groups
