"""Speech to text with timestamps.

The default runs faster-whisper on the worker, so a lecture recording never leaves our server
and costs nothing per minute. A hosted service (with speaker labels) can implement the same
Transcriber interface later.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import Settings
from app.ingestion.base import ExtractionError

log = logging.getLogger(__name__)


@dataclass
class Utterance:
    start: float
    end: float
    text: str
    speaker: str | None = None  # set by transcribers that can tell speakers apart


@dataclass
class Transcript:
    utterances: list[Utterance]
    language: str | None = None


class Transcriber(Protocol):
    def transcribe(self, audio: Path, on_progress: Callable[[float], None]) -> Transcript:
        """audio is 16 kHz mono WAV. on_progress gets the seconds transcribed so far."""
        ...


# Whisper sometimes "hears" these in silence or music. A whole utterance that is only one of
# them is dropped; real speech that happens to contain the words is kept.
_HALLUCINATIONS = {
    "thank you.",
    "thanks for watching!",
    "thank you for watching.",
    "thanks for watching.",
    "please subscribe.",
    "you",
    ".",
}


class WhisperTranscriber:
    _models: dict[tuple[str, str, str], object] = {}
    _lock = threading.Lock()

    def __init__(self, settings: Settings):
        self.settings = settings

    def _model(self):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - installed in the worker image
            raise ExtractionError(
                "transcription_unavailable", "Transcribing recordings is not set up on this server."
            ) from exc
        s = self.settings
        key = (s.whisper_model, s.whisper_device, s.whisper_compute_type)
        with self._lock:
            if key not in self._models:
                log.info("loading whisper model %s on %s", s.whisper_model, s.whisper_device)
                self._models[key] = WhisperModel(
                    s.whisper_model,
                    device=s.whisper_device,
                    compute_type=s.whisper_compute_type,
                    download_root=s.whisper_cache_dir,
                )
            return self._models[key]

    def transcribe(self, audio: Path, on_progress: Callable[[float], None]) -> Transcript:
        model = self._model()
        pieces, info = model.transcribe(
            str(audio),
            beam_size=5,
            vad_filter=True,  # skips silence, which is where Whisper invents text
            condition_on_previous_text=False,  # stops one mistake repeating for minutes
        )
        utterances = []
        for piece in pieces:
            on_progress(piece.end)
            text = piece.text.strip()
            if not text or piece.no_speech_prob > 0.8:
                continue
            if text.lower() in _HALLUCINATIONS:
                continue
            utterances.append(Utterance(start=round(piece.start, 2), end=round(piece.end, 2), text=text))
        return Transcript(utterances=utterances, language=info.language)
