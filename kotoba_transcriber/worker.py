"""GUI スレッドをブロックしないよう、文字起こしを別スレッドで回す。"""

from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from . import formatters
from .audio import load_waveform
from .config import DiarizationOptions, OutputOptions
from .diarization import Diarizer, DiarizationUnavailable, assign_speakers
from .transcriber import Cancelled, Segment, Transcriber

# 1 ファイルの進捗の内訳。話者分離の有無で配分を変える。
_PHASES_PLAIN = {"decode": 0.12, "diarize": 0.0, "transcribe": 0.86}
_PHASES_DIARIZED = {"decode": 0.08, "diarize": 0.37, "transcribe": 0.53}


class TranscribeWorker(QObject):
    """ファイルを 1 つずつ処理する。QThread へ moveToThread して使う。"""

    log = Signal(str)
    diarization_disabled = Signal(str)
    file_started = Signal(int)
    file_progress = Signal(int, float)
    file_finished = Signal(int, list)
    file_failed = Signal(int, str)
    finished = Signal(bool)  # True なら中断された

    def __init__(
        self,
        files: list[Path],
        options: OutputOptions,
        diarization: DiarizationOptions,
        model_id: str,
        language: str | None,
        transcriber: Transcriber,
        diarizer: Diarizer,
    ) -> None:
        super().__init__()
        self._files = list(files)
        self._options = options
        self._diarization = diarization
        self._model_id = model_id
        self._language = language
        self._transcriber = transcriber
        self._diarizer = diarizer
        self._cancel = threading.Event()
        self._phases = _PHASES_DIARIZED if diarization.enabled else _PHASES_PLAIN

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    @Slot()
    def run(self) -> None:
        try:
            self._transcriber.load(self._model_id, self._language, self.log.emit)
        except Exception as exc:
            self.log.emit(f"[エラー] モデルを読み込めませんでした: {exc}")
            self.log.emit(traceback.format_exc())
            self.finished.emit(self._cancel.is_set())
            return

        if self._diarization.enabled:
            try:
                self._diarizer.load(self.log.emit)
            except DiarizationUnavailable as exc:
                # 話者分離だけ諦めて、文字起こしは続ける。
                # 明示的に有効にされた機能を黙って落とさないよう、画面にも知らせる。
                self._disable_diarization(str(exc))
            except Exception as exc:
                self.log.emit(traceback.format_exc())
                self._disable_diarization(f"予期しないエラー: {exc}")

        for index, path in enumerate(self._files):
            if self._cancel.is_set():
                break
            self.file_started.emit(index)
            self.log.emit(f"開始: {path.name}")
            started_at = time.monotonic()
            try:
                outputs = self._process(index, path)
            except Cancelled:
                self.log.emit("中断しました。")
                break
            except Exception as exc:
                self.file_failed.emit(index, str(exc))
                self.log.emit(f"[エラー] {path.name}: {exc}")
                self.log.emit(traceback.format_exc())
                continue

            elapsed = time.monotonic() - started_at
            self.file_finished.emit(index, [str(p) for p in outputs])
            self.log.emit(f"完了: {path.name} ({elapsed:.1f} 秒)")
            for output in outputs:
                self.log.emit(f"  -> {output}")

        self.finished.emit(self._cancel.is_set())

    def _disable_diarization(self, reason: str) -> None:
        self.log.emit(f"[話者分離を無効にします] {reason}")
        self.diarization_disabled.emit(reason)
        self._diarization = DiarizationOptions(enabled=False)
        self._phases = _PHASES_PLAIN

    def _process(self, index: int, path: Path) -> list[Path]:
        phases = self._phases
        decode_end = phases["decode"]
        diarize_end = decode_end + phases["diarize"]
        transcribe_end = diarize_end + phases["transcribe"]

        def phase_progress(low: float, high: float):
            def report(ratio: float) -> None:
                self.file_progress.emit(index, low + ratio * (high - low))

            return report

        waveform = load_waveform(path, progress=phase_progress(0.0, decode_end))
        if self._cancel.is_set():
            raise Cancelled

        minutes = waveform.size / 16_000 / 60
        self.log.emit(f"  音声長: {minutes:.1f} 分")

        turns = []
        if self._diarization.enabled:
            self.log.emit("  話者分離を実行しています...")
            turns = self._diarizer.diarize(
                waveform,
                num_speakers=self._diarization.num_speakers,
                progress=phase_progress(decode_end, diarize_end),
            )
            speakers = len({turn.speaker for turn in turns})
            self.log.emit(f"  話者 {speakers} 人 / 区間 {len(turns)} 件を検出しました")
            if self._cancel.is_set():
                raise Cancelled

        segments = self._transcriber.transcribe(
            waveform,
            progress=phase_progress(diarize_end, transcribe_end),
            should_cancel=self._cancel.is_set,
        )
        if self._cancel.is_set():
            raise Cancelled

        if turns:
            segments = assign_speakers(segments, turns)

        outputs = self._write_outputs(path, segments)
        self.file_progress.emit(index, 1.0)
        return outputs

    def _write_outputs(self, source: Path, segments: list[Segment]) -> list[Path]:
        target_dir = self._options.output_dir or source.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        options = self._options

        # 整形は選ばれた形式だけ実行したいので、生成は遅延させる。
        planned = (
            (options.plain_text, f"{source.stem}.txt",
             lambda: formatters.to_plain_text(segments)),
            (options.timestamped, f"{source.stem}_timestamp.txt",
             lambda: formatters.to_timestamped_text(segments)),
            (options.srt, f"{source.stem}.srt",
             lambda: formatters.to_srt(segments)),
            (options.vtt, f"{source.stem}.vtt",
             lambda: formatters.to_vtt(segments)),
            (options.json, f"{source.stem}.json",
             lambda: formatters.to_json(
                 segments, source=str(source), model=self._model_id)),
        )

        written: list[Path] = []
        for enabled, name, render in planned:
            if enabled:
                written.append(_write(_unique_path(target_dir / name), render()))
        return written


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8", newline="\r\n")
    return path


def _unique_path(path: Path) -> Path:
    """同名ファイルがあれば `name (2).txt` のように退避する。"""
    if not path.exists():
        return path
    for counter in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
    return path
