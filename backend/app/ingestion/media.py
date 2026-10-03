"""Audio and video: lecture recordings, class videos and voice memos.

Audio: ffmpeg converts to 16 kHz mono, then the transcriber turns speech into timed text.
Video: the same for the soundtrack, plus the slides and boards. Tiny thumbnails are taken
from the video's keyframes; when the picture changes and then holds still, the last frame of that still
stretch (the fullest version of a slide that builds up) is read by Claude's vision. On-screen
text and diagrams go into the material at the time they appeared, so the notes do not depend on
the transcript alone.
"""

import json
import logging
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from app.ingestion.base import Block, ExtractionError, ExtractResult, ExtractTools
from app.ingestion.segment import clock
from app.ingestion.vision import SCREEN_PICTURE_PREFIX, ScreenRead, read_frames

log = logging.getLogger(__name__)

SAMPLE_SECONDS = 2  # at most one thumbnail every 2 s
THUMB_W, THUMB_H = 32, 18
CHANGE_THRESHOLD = 10.0  # mean colour difference (0-255 per channel) that counts as a new picture
MIN_STILL_SECONDS = 8  # shorter stretches are transitions or camera moves


@dataclass
class Probe:
    duration: float
    has_audio: bool
    has_video: bool


def probe(path: Path) -> Probe:
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_entries",
                "format=duration:stream=codec_type:stream_disposition=attached_pic",
                str(path),
            ],
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout
        info = json.loads(out)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ExtractionError(
            "unreadable_media",
            "This recording could not be opened. It may be damaged or in an unusual format.",
        ) from exc
    streams = info.get("streams", [])
    duration = float(info.get("format", {}).get("duration") or 0)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    # Cover art in an MP3 shows up as a one-frame video stream.
    has_video = any(
        s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")
        for s in streams
    )
    return Probe(duration=duration, has_audio=has_audio, has_video=has_video)


def _check_length(p: Probe, tools: ExtractTools) -> None:
    limit = tools.settings.max_media_minutes
    if p.duration <= 0:
        raise ExtractionError("unreadable_media", "This recording seems to be empty.")
    if p.duration > limit * 60:
        raise ExtractionError(
            "source_too_long",
            f"This recording is {clock(p.duration)} long. The limit is {limit} minutes per guide; "
            "split it into parts and upload each one.",
        )


def _ffmpeg(args: list[str], timeout: float, loglevel: str = "error") -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-v", loglevel, *args],
            check=True,
            timeout=timeout,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        log.warning("ffmpeg failed: %s", exc.stderr[-500:] if exc.stderr else exc)
        raise ExtractionError("unreadable_media", "This recording could not be processed.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ExtractionError("unreadable_media", "Processing this recording took too long.") from exc


def _transcribe(path: Path, p: Probe, tools: ExtractTools, workdir: Path) -> list[Block]:
    if tools.transcriber is None:
        raise ExtractionError(
            "transcription_unavailable", "Transcribing recordings is not set up on this server."
        )
    wav = workdir / "audio.wav"
    tools.progress("Preparing the audio")
    _ffmpeg(["-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(wav)], timeout=1800)
    last = 0.0

    def on_progress(seconds: float) -> None:
        nonlocal last
        if time.monotonic() - last >= 20:
            last = time.monotonic()
            tools.progress(f"Transcribed {clock(seconds)} of {clock(p.duration)}")

    transcript = tools.transcriber.transcribe(wav, on_progress)
    return [
        Block(text=u.text, kind="speech", start=u.start, end=u.end)
        for u in transcript.utterances
        if u.text.strip()
    ]


def still_stretches(
    thumbs: list[bytes], times: list[float], duration: float
) -> list[tuple[float, float, int]]:
    """(start s, end s, index of the frame to read) for each stretch where the picture holds still.

    The frame read is the last of the stretch: a slide that builds up bullet by bullet is complete there.
    """
    stretches: list[tuple[int, int]] = []
    first = 0
    for i in range(1, len(thumbs) + 1):
        if i == len(thumbs) or _diff(thumbs[i], thumbs[first]) > CHANGE_THRESHOLD:
            stretches.append((first, i - 1))
            first = i
    out = []
    for a, b in stretches:
        start = times[a]
        end = times[b + 1] if b + 1 < len(times) else duration
        if end - start >= MIN_STILL_SECONDS:
            out.append((start, end, b))
    return out


def _diff(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b, strict=False)) / max(1, len(a))


_PTS = re.compile(rb"Parsed_showinfo.*?\bpts_time:\s*([0-9.]+)")


def _key_frames(path: Path, p: Probe, tools: ExtractTools, workdir: Path) -> list[tuple[float, float, bytes]]:
    """(start, end, JPEG) for each distinct still picture, at most max_video_frames of them."""
    tools.progress("Looking for slides and boards")
    frame_bytes = THUMB_W * THUMB_H * 3
    result = _ffmpeg(
        [
            # Only keyframes are decoded (many times faster), at most one every SAMPLE_SECONDS.
            # showinfo reports each one's exact time, so the frame read later is the one compared.
            "-skip_frame",
            "nokey",
            "-i",
            str(path),
            "-an",
            "-vf",
            f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{SAMPLE_SECONDS})',"
            f"scale={THUMB_W}:{THUMB_H}:flags=area,format=rgb24,showinfo",
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        timeout=1800,
        loglevel="info",
    )
    raw = result.stdout
    times = [float(t) for t in _PTS.findall(result.stderr)]
    thumbs = [raw[i : i + frame_bytes] for i in range(0, len(raw) - frame_bytes + 1, frame_bytes)]
    count = min(len(times), len(thumbs))
    stretches = still_stretches(thumbs[:count], times[:count], p.duration)
    limit = tools.settings.max_video_frames
    if len(stretches) > limit:
        # Keep the pictures that stayed up longest: slides, not camera moves.
        stretches = sorted(sorted(stretches, key=lambda s: s[1] - s[0], reverse=True)[:limit])
    frames = []
    for n, (start, end, index) in enumerate(stretches):
        out = workdir / f"frame{n:04d}.jpg"
        _ffmpeg(
            [
                "-ss",
                f"{times[index]:.3f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-vf",
                "scale='min(1568,iw)':-2",
                "-q:v",
                "3",
                str(out),
            ],
            timeout=120,
        )
        if out.exists():
            frames.append((round(start, 2), round(min(end, p.duration), 2), out.read_bytes()))
    return frames


def _screen_blocks(frames: list[tuple[float, float, bytes]], tools: ExtractTools) -> list[Block]:
    if not frames:
        return []
    ends = {start: end for start, end, _ in frames}
    reads = read_frames(tools, [(start, image) for start, _, image in frames])
    blocks: list[Block] = []
    previous = ""
    for start, read in reads:
        text = screen_text(read)
        key = " ".join(text.lower().split())
        if key == previous:  # the same slide again after a camera cut
            blocks[-1].end = ends[start]
            continue
        previous = key
        blocks.append(Block(text=text, kind="on_screen", start=start, end=ends[start]))
    return blocks


def screen_text(read: ScreenRead) -> str:
    parts = []
    title = read.title.strip()
    body = read.text.strip()
    if title and body.split("\n", 1)[0].strip() != title:
        parts.append(title)
    if body:
        parts.append(body)
    if read.picture.strip():
        parts.append(SCREEN_PICTURE_PREFIX + read.picture.strip())
    return "\n".join(parts)


class AudioExtractor:
    kinds = ("audio",)

    def __init__(self, tools: ExtractTools):
        self.tools = tools

    def extract_file(self, path: Path) -> ExtractResult:
        p = probe(path)
        if not p.has_audio:
            raise ExtractionError("no_audio", "This file has no sound to transcribe.")
        _check_length(p, self.tools)
        with tempfile.TemporaryDirectory(prefix="hsn-audio-") as tmp:
            blocks = _transcribe(path, p, self.tools, Path(tmp))
        return ExtractResult(blocks=blocks, timed=True, duration=p.duration, media="audio")


class VideoExtractor:
    kinds = ("video",)

    def __init__(self, tools: ExtractTools):
        self.tools = tools

    def extract_file(self, path: Path) -> ExtractResult:
        p = probe(path)
        if not p.has_video:
            return AudioExtractor(self.tools).extract_file(path)
        _check_length(p, self.tools)
        warnings = []
        with tempfile.TemporaryDirectory(prefix="hsn-video-") as tmp:
            workdir = Path(tmp)
            speech = _transcribe(path, p, self.tools, workdir) if p.has_audio else []
            screen: list[Block] = []
            if self.tools.vision is not None and self.tools.settings.vision_enabled:
                screen = _screen_blocks(_key_frames(path, p, self.tools, workdir), self.tools)
            else:
                warnings.append(
                    {
                        "code": "screen_skipped",
                        "message": "Only the speech was used; reading slides is turned off on this server.",
                    }
                )
        if not p.has_audio:
            warnings.append(
                {"code": "no_audio", "message": "This video has no sound; only what is on screen was used."}
            )
        blocks = sorted(speech + screen, key=lambda b: (b.start or 0.0, b.kind != "on_screen"))
        usage = self.tools.usage.as_dict() if self.tools.usage else {}
        return ExtractResult(
            blocks=blocks, timed=True, duration=p.duration, media="video", warnings=warnings, usage=usage
        )
