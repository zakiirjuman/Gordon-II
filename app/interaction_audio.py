from __future__ import annotations

import re
import subprocess
import tempfile
import wave
from pathlib import Path


def wav_duration_seconds(path: str | Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def detect_speech_regions(
    wav_path: str | Path,
    *,
    silence_db: float = -35.0,
    min_silence_s: float = 0.45,
    min_speech_s: float = 0.35,
) -> list[tuple[float, float]]:
    duration = wav_duration_seconds(wav_path)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(wav_path),
            "-af",
            f"silencedetect=noise={silence_db}dB:d={min_silence_s}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stderr or "") + (proc.stdout or "")
    silence_starts = [
        float(match.group(1))
        for match in re.finditer(r"silence_start:\s*([0-9.]+)", output)
    ]
    silence_ends = [
        float(match.group(1))
        for match in re.finditer(r"silence_end:\s*([0-9.]+)", output)
    ]

    speech_regions: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in zip(silence_starts, silence_ends):
        if start - cursor >= min_speech_s:
            speech_regions.append((cursor, start))
        cursor = end
    if duration - cursor >= min_speech_s:
        speech_regions.append((cursor, duration))

    if not speech_regions and duration >= min_speech_s:
        speech_regions.append((0.0, duration))
    return speech_regions


def extract_segment(
    wav_path: str | Path,
    start_s: float,
    end_s: float,
) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(wav_path),
            "-ss",
            f"{start_s:.3f}",
            "-to",
            f"{end_s:.3f}",
            "-ac",
            "1",
            "-ar",
            "16000",
            tmp.name,
        ],
        check=True,
        capture_output=True,
    )
    return tmp.name
