"""アプリ全体で共有する設定値。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Kotoba Transcriber"
ORG_NAME = "hiroto"

# Whisper 系の入力サンプリングレート。
TARGET_SR = 16_000

# pipeline へ一度に渡す音声の長さ。進捗表示の粒度とメモリ使用量を決める。
SEGMENT_SECONDS = 300.0
# 分割位置を無音に寄せるために前後を探索する幅。
SPLIT_SEARCH_SECONDS = 15.0
# 無音判定に使う窓の長さ。
SPLIT_WINDOW_SECONDS = 0.4


# --------------------------------------------------------------------- モデル


@dataclass(frozen=True)
class ModelChoice:
    """選択できる文字起こしモデル。

    `chunk_length_s` はモデルごとの推奨値。kotoba-whisper のような蒸留モデルは
    15 秒、本家 Whisper は学習時と同じ 30 秒が良い。
    """

    model_id: str
    label: str
    chunk_length_s: float
    batch_size: int
    note: str


MODELS: tuple[ModelChoice, ...] = (
    ModelChoice(
        "kotoba-tech/kotoba-whisper-v2.0",
        "kotoba-whisper v2.0（日本語特化・推奨）",
        15.0,
        16,
        "日本語に特化した蒸留モデル。速度と精度のバランスが最良",
    ),
    ModelChoice(
        "kotoba-tech/kotoba-whisper-v1.0",
        "kotoba-whisper v1.0",
        15.0,
        16,
        "v2.0 の前世代。比較用",
    ),
    ModelChoice(
        "openai/whisper-large-v3-turbo",
        "Whisper large-v3-turbo（多言語・高速）",
        30.0,
        16,
        "多言語対応。large-v3 よりかなり速い",
    ),
    ModelChoice(
        "openai/whisper-large-v3",
        "Whisper large-v3（多言語・最高精度）",
        30.0,
        8,
        "最も重い。時間と VRAM に余裕があるとき",
    ),
    ModelChoice(
        "openai/whisper-medium",
        "Whisper medium（軽量）",
        30.0,
        16,
        "VRAM が少ない環境向け",
    ),
)

DEFAULT_MODEL_ID = MODELS[0].model_id


def model_for(model_id: str) -> ModelChoice:
    """モデル ID から設定を引く。一覧にない ID なら Whisper 相当の既定値。"""
    for choice in MODELS:
        if choice.model_id == model_id:
            return choice
    return ModelChoice(model_id, model_id, 30.0, 8, "手入力されたモデル")


LANGUAGES: tuple[tuple[str, str | None], ...] = (
    ("日本語", "ja"),
    ("英語", "en"),
    ("自動判定", None),
)


# ----------------------------------------------------------------- 話者分離

# pyannote の話者分離パイプライン。Hugging Face 上で利用条件への同意が必要。
DIARIZATION_MODEL_ID = "pyannote/speaker-diarization-3.1"


@dataclass
class DiarizationOptions:
    enabled: bool = False
    # 0 なら話者数を推定させる。
    num_speakers: int = 0


# ------------------------------------------------------------------- 出力


@dataclass
class OutputOptions:
    """書き出しに関する設定。"""

    plain_text: bool = True
    timestamped: bool = True
    srt: bool = False
    vtt: bool = False
    json: bool = False
    # None なら入力ファイルと同じフォルダへ書き出す。
    output_dir: Path | None = None

    @property
    def any_selected(self) -> bool:
        return any((self.plain_text, self.timestamped, self.srt, self.vtt, self.json))


# 出力形式の (設定属性名, 画面表示, ファイル名サフィックス) 一覧。
OUTPUT_FORMATS: tuple[tuple[str, str, str], ...] = (
    ("plain_text", "プレーンテキスト", ".txt"),
    ("timestamped", "タイムスタンプ付き", "_timestamp.txt"),
    ("srt", "SRT 字幕", ".srt"),
    ("vtt", "WebVTT 字幕", ".vtt"),
    ("json", "JSON（生データ）", ".json"),
)


# ------------------------------------------------------------------- 入力

MEDIA_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".oga", ".opus", ".wma",
    ".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm", ".ts", ".mts",
}

FILE_DIALOG_FILTER = (
    "音声・動画ファイル (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.oga *.opus *.wma "
    "*.mp4 *.m4v *.mov *.mkv *.avi *.webm *.ts *.mts);;すべてのファイル (*.*)"
)
