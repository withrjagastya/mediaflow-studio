"""FFmpeg helpers, media discovery and preset validation.

FFmpeg runs locally. No files or metadata leave the computer.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"})
DEFAULT_PRESETS = {
    "reel": {"width": 1080, "height": 1920, "description": "Vertical 9:16 Reel / Short"},
    "square": {"width": 1080, "height": 1080, "description": "Square 1:1 post"},
    "landscape": {"width": 1920, "height": 1080, "description": "Landscape 16:9 video"},
    "preview": {"width": 640, "height": 360, "description": "Small 16:9 review copy"},
}


@dataclass
class MediaInfo:
    path: str
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool
    size_bytes: int

    def to_dict(self):
        return asdict(self)


def binaries_available():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run_command(args: list[str]) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing required executable: {args[0]}") from exc
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "Unknown FFmpeg error").strip()
        raise RuntimeError(f"Command failed ({result.returncode}): {msg[-1600:]}")
    return result


def probe_media(path: Path) -> MediaInfo:
    if not path.is_file():
        raise FileNotFoundError(f"Media file not found: {path}")
    result = run_command([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"No video stream found in {path.name}")
    aud = any(s.get("codec_type") == "audio" for s in streams)
    duration_text = payload.get("format", {}).get("duration") or video.get("duration") or "0"
    try:
        fps = float(Fraction(str(video.get("avg_frame_rate") or "0")))
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return MediaInfo(
        path=str(path.resolve()), width=int(video.get("width") or 0),
        height=int(video.get("height") or 0), duration=float(duration_text),
        fps=round(fps, 3), has_audio=aud, size_bytes=path.stat().st_size,
    )


def find_videos(folder: Path, recursive: bool = True, excluded_folder: Path | None = None) -> list[Path]:
    if not folder.is_dir():
        raise NotADirectoryError(f"Input directory does not exist: {folder}")
    excluded = excluded_folder.resolve() if excluded_folder else None
    candidates = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        (f for f in candidates if f.is_file() and not f.is_symlink()
         and f.suffix.lower() in VIDEO_EXTENSIONS
         and (excluded is None or not f.resolve().is_relative_to(excluded))),
        key=lambda x: str(x).lower(),
    )


def safe_stem(name: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-_")
    return stem[:64] or "video"


def source_id(path: Path) -> str:
    # Input path + extension prevent collisions for "clip.mp4" and "clip.mov".
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{safe_stem(path.stem)}-{digest}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filter_graph(width: int, height: int, mode: str = "pad") -> str:
    if mode not in {"pad", "crop"}:
        raise ValueError("mode must be 'pad' or 'crop'")
    if mode == "crop":
        return (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1,format=yuv420p")
    return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p")


def load_presets(file_path: Path | None = None) -> dict:
    presets = DEFAULT_PRESETS if file_path is None else json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(presets, dict) or not presets:
        raise ValueError("Preset file must contain a non-empty JSON object")
    for name, preset in presets.items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", name):
            raise ValueError(f"Invalid preset name: {name!r}")
        if not isinstance(preset, dict):
            raise ValueError(f"Preset {name} must be an object")
        for key in ("width", "height"):
            value = preset.get(key)
            if type(value) is not int or not 2 <= value <= 4096 or value % 2:
                raise ValueError(f"Preset {name}: {key} must be an even number from 2 to 4096")
    return presets
