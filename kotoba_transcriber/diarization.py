"""pyannote.audio による話者分離と、文字起こし結果への話者ラベル付与。

pyannote は重い依存なので import はすべて関数の中で行う。話者分離を使わない
限りロードされないようにして、起動時間とメモリを無駄にしない。
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Iterable, Sequence

from .config import DIARIZATION_MODEL_ID, TARGET_SR
from .transcriber import Segment

LogFn = Callable[[str], None]
ProgressFn = Callable[[float], None]

_TOKEN_ENV_VARS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACEHUB_API_TOKEN")

# pyannote.audio 4.x は speaker-diarization-3.1 を読むときに
# speaker-diarization-community-1 の資産（xvec_transform.npz など）も取りにいく。
# どれか 1 つでも未同意だとロードに失敗するので、3 つとも案内する。
GATED_REPOS = (
    "pyannote/speaker-diarization-3.1",
    "pyannote/segmentation-3.0",
    "pyannote/speaker-diarization-community-1",
)

_TOKEN_HELP = (
    "話者分離には Hugging Face のアクセストークンと、モデルの利用条件への同意が必要です。\n"
    "  1. 次のページをすべて開いて利用条件に同意する（無料）\n"
    + "".join(f"       https://huggingface.co/{repo}\n" for repo in GATED_REPOS)
    + "  2. https://huggingface.co/settings/tokens で read 権限のトークンを作る\n"
    "  3. PowerShell で次を実行する\n"
    '     & "$env:USERPROFILE\\.venvs\\kotoba-transcriber\\Scripts\\hf.exe" auth login\n'
    "     （または環境変数 HF_TOKEN にトークンを設定する）"
)


class DiarizationUnavailable(RuntimeError):
    """話者分離を実行できない（未インストール、トークンなし、など）。"""


@dataclass(frozen=True)
class Turn:
    """ある話者が話していた区間。"""

    start: float
    end: float
    speaker: str


def resolve_token() -> str | None:
    """環境変数か huggingface_hub のログイン情報からトークンを探す。"""
    for name in _TOKEN_ENV_VARS:
        value = os.environ.get(name)
        if value:
            return value
    try:
        from huggingface_hub import get_token

        return get_token()
    except Exception:
        return None


def _import_pyannote():
    """pyannote.audio を読み込む。

    torchcodec（ffmpeg の共有ライブラリを要求する）が入っていないと import 時に
    長い警告が出るが、こちらは波形をメモリ上の dict で渡すので影響がない。
    紛らわしいので黙らせる。
    """
    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*torchcodec.*")
        from pyannote.audio import Pipeline

        return Pipeline


@lru_cache(maxsize=1)
def is_available() -> bool:
    """pyannote.audio が入っているか。

    実際に import すると lightning などまで読み込まれて数秒かかるので、
    UI の有効・無効を決めるだけのここでは spec の有無しか見ない。
    読み込みに失敗する場合は `Diarizer.load()` がエラーを返す。
    """
    try:
        return importlib.util.find_spec("pyannote.audio") is not None
    except Exception:
        return False


class Diarizer:
    """話者分離パイプラインを保持して使い回す。"""

    def __init__(self, model_id: str = DIARIZATION_MODEL_ID) -> None:
        self.model_id = model_id
        self._pipeline = None

    @property
    def is_loaded(self) -> bool:
        return self._pipeline is not None

    def load(self, log: LogFn | None = None) -> None:
        if self._pipeline is not None:
            return

        try:
            Pipeline = _import_pyannote()
        except Exception as exc:
            raise DiarizationUnavailable(
                "pyannote.audio が読み込めません。"
                "setup.bat を実行し直すか、pip install pyannote.audio してください。"
                f"（{exc}）"
            ) from exc

        token = resolve_token()
        if not token:
            raise DiarizationUnavailable(_TOKEN_HELP)

        if log:
            log(f"話者分離モデルを読み込んでいます: {self.model_id}")

        try:
            pipeline = _from_pretrained(Pipeline, self.model_id, token)
        except Exception as exc:
            raise DiarizationUnavailable(
                f"話者分離モデルを取得できませんでした: {exc}\n{_TOKEN_HELP}"
            ) from exc

        if pipeline is None:
            raise DiarizationUnavailable(
                "話者分離モデルを取得できませんでした（利用条件に未同意の可能性があります）。\n"
                + _TOKEN_HELP
            )

        try:
            import torch

            if torch.cuda.is_available():
                pipeline.to(torch.device("cuda"))
        except Exception as exc:  # GPU に載らなくても CPU で続行する
            if log:
                log(f"話者分離を GPU に載せられませんでした。CPU で実行します（{exc}）")

        self._pipeline = pipeline
        if log:
            log("話者分離モデルの読み込みが完了しました。")

    def unload(self) -> None:
        self._pipeline = None

    def diarize(
        self,
        waveform,
        sample_rate: int = TARGET_SR,
        num_speakers: int = 0,
        progress: ProgressFn | None = None,
    ) -> list[Turn]:
        if self._pipeline is None:
            raise RuntimeError("話者分離モデルが読み込まれていません")

        import torch

        tensor = torch.from_numpy(waveform).unsqueeze(0)
        payload = {"waveform": tensor, "sample_rate": sample_rate}

        kwargs = {}
        if num_speakers > 0:
            kwargs["num_speakers"] = num_speakers

        hook = _ProgressHook(progress) if progress else None
        if hook is not None:
            kwargs["hook"] = hook

        try:
            result = self._pipeline(payload, **kwargs)
        except TypeError:
            # hook を受け付けない版のための保険。
            kwargs.pop("hook", None)
            result = self._pipeline(payload, **kwargs)

        annotation = _to_annotation(result)
        turns = [
            Turn(float(segment.start), float(segment.end), str(speaker))
            for segment, _, speaker in annotation.itertracks(yield_label=True)
        ]
        turns.sort(key=lambda t: t.start)
        if progress:
            progress(1.0)
        return turns


def _to_annotation(result):
    """パイプラインの戻り値から `Annotation` を取り出す。

    pyannote.audio 3.x は `Annotation` をそのまま返すが、4.x は `DiarizeOutput`
    という入れ物を返す。4.x では重なりを排除した
    `exclusive_speaker_diarization` を優先する（1 つの発話に 1 人を割り当てる
    用途なので、同時発話を分けてもらう必要がない）。
    """
    for attribute in ("exclusive_speaker_diarization", "speaker_diarization"):
        annotation = getattr(result, attribute, None)
        if annotation is not None and hasattr(annotation, "itertracks"):
            return annotation
    if hasattr(result, "itertracks"):
        return result
    raise RuntimeError(
        f"話者分離の結果を解釈できません: {type(result).__name__}"
    )


def _from_pretrained(pipeline_cls, model_id: str, token: str):
    """pyannote のバージョン差（token / use_auth_token）を吸収する。"""
    try:
        return pipeline_cls.from_pretrained(model_id, token=token)
    except TypeError:
        return pipeline_cls.from_pretrained(model_id, use_auth_token=token)


class _ProgressHook:
    """pyannote の hook を 0.0-1.0 の進捗に変換する。"""

    def __init__(self, progress: ProgressFn) -> None:
        self._progress = progress

    def __call__(self, step_name, step_artifact, file=None, total=None, completed=None):
        if total:
            self._progress(min(1.0, (completed or 0) / total))

    # `with hook:` の形で使われても壊れないようにしておく。
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def assign_speakers(
    segments: Sequence[Segment],
    turns: Sequence[Turn],
) -> list[Segment]:
    """各発話に、時間の重なりが最も大きい話者を割り当てる。

    話者ラベルは登場順に「話者1」「話者2」…へ振り直す。pyannote が返す
    `SPEAKER_00` のままだと読みにくいため。
    """
    if not turns:
        return list(segments)

    names = _speaker_names(turns)
    labelled: list[Segment] = []
    for segment in segments:
        speaker = _dominant_speaker(segment, turns)
        labelled.append(
            Segment(
                start=segment.start,
                end=segment.end,
                text=segment.text,
                speaker=names.get(speaker) if speaker else None,
            )
        )
    return labelled


def _speaker_names(turns: Sequence[Turn]) -> dict[str, str]:
    order: list[str] = []
    for turn in turns:
        if turn.speaker not in order:
            order.append(turn.speaker)
    return {raw: f"話者{index}" for index, raw in enumerate(order, start=1)}


def _dominant_speaker(segment: Segment, turns: Iterable[Turn]) -> str | None:
    best_speaker: str | None = None
    best_overlap = 0.0
    totals: dict[str, float] = {}
    for turn in turns:
        overlap = min(segment.end, turn.end) - max(segment.start, turn.start)
        if overlap <= 0:
            continue
        total = totals.get(turn.speaker, 0.0) + overlap
        totals[turn.speaker] = total
        if total > best_overlap:
            best_overlap = total
            best_speaker = turn.speaker

    if best_speaker is not None:
        return best_speaker

    # まったく重ならない場合は中心時刻に最も近い区間の話者を使う。
    center = (segment.start + segment.end) / 2
    nearest = min(
        turns,
        key=lambda t: 0.0 if t.start <= center <= t.end else min(
            abs(center - t.start), abs(center - t.end)
        ),
        default=None,
    )
    return nearest.speaker if nearest else None
