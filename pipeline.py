"""Robust batch-production pipeline with resumable outputs and a QC manifest."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import os
import subprocess
import tempfile

from .core import (
    find_videos, filter_graph, load_presets, probe_media,
    run_command, sha256_file, source_id,
)


def encode(source: Path, dest: Path, width: int, height: int, mode: str,
           crf: int, overwrite: bool) -> str:
    if dest.exists() and not overwrite:
        return "skipped-existing"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Encode to a temporary file first so failures cannot leave a corrupt final MP4.
    with tempfile.NamedTemporaryFile(dir=dest.parent, prefix=".render-", suffix=".mp4", delete=False) as fh:
        tmp = Path(fh.name)
    try:
        run_command([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-map", "0:v:0", "-map", "0:a:0?", "-vf", filter_graph(width, height, mode),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmp),
        ])
        os.replace(tmp, dest)
        return "created"
    finally:
        if tmp.exists():
            tmp.unlink()


def generate_thumbnail(source: Path, destination: Path, timestamp: float, overwrite: bool):
    if destination.exists() and not overwrite:
        return "skipped-existing"
    destination.parent.mkdir(parents=True, exist_ok=True)
    run_command([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(max(0.0, timestamp)), "-i", str(source),
        "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", str(destination),
    ])
    if not destination.exists():
        raise RuntimeError("Thumbnail generation returned no image")
    return "created"


def build_one(source: Path, output: Path, requested: list[str], presets: dict, mode: str,
              crf: int, overwrite: bool, thumbs: bool, checksum: bool) -> dict:
    record = {"source": str(source.resolve()), "id": source_id(source),
              "status": "ok", "error": "", "source_info": None, "checksum_sha256": None,
              "outputs": [], "thumbnail": None}
    try:
        info = probe_media(source)
        record["source_info"] = info.to_dict()
        if checksum:
            record["checksum_sha256"] = sha256_file(source)
        if info.duration <= 0 or info.width < 1 or info.height < 1:
            raise ValueError("Source has invalid video duration or dimensions")
        for name in requested:
            preset = presets[name]
            target = output / "videos" / name / f"{record['id']}-{name}.mp4"
            try:
                result = encode(source, target, preset["width"], preset["height"], mode, crf, overwrite)
                rendered = probe_media(target)
                qc_ok = (rendered.width == preset["width"] and rendered.height == preset["height"]
                         and abs(rendered.duration - info.duration) <= max(0.6, info.duration * 0.03))
                record["outputs"].append({"preset": name, "path": str(target.resolve()),
                                          "result": result, "qc_pass": qc_ok, "info": rendered.to_dict()})
                if not qc_ok:
                    record["status"] = "warning"
            except Exception as exc:
                record["status"] = "error"
                record["outputs"].append({"preset": name, "path": str(target.resolve()),
                                          "result": "error", "error": str(exc)})
        if thumbs:
            thumb = output / "thumbnails" / f"{record['id']}.jpg"
            try:
                generate_thumbnail(source, thumb, min(5.0, info.duration * 0.25), overwrite)
                record["thumbnail"] = str(thumb.resolve())
            except Exception as exc:
                record["status"] = "error"
                record["error"] = f"Thumbnail: {exc}"
    except Exception as exc:
        record["status"] = "error"
        record["error"] = str(exc)
    return record


def write_report(output: Path, records: list[dict], settings: dict) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    report = {"format_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "settings": settings, "records": records}
    manifest = output / "mediaflow-report.json"
    manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    csv_path = output / "mediaflow-report.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["source", "status", "preset", "output", "result", "qc_pass", "error"])
        for record in records:
            for out in record["outputs"] or [{}]:
                writer.writerow([record["source"], record["status"], out.get("preset", ""),
                                 out.get("path", ""), out.get("result", ""),
                                 out.get("qc_pass", ""), out.get("error", record["error"])])
    return manifest


def build(input_path: Path, output_path: Path, presets_to_use: list[str], mode: str = "pad",
          crf: int = 24, workers: int = 1, overwrite: bool = False,
          thumbs: bool = True, checksum: bool = False,
          preset_file: Path | None = None, recursive: bool = True,
          progress=None) -> dict:
    presets = load_presets(preset_file)
    if not presets_to_use:
        raise ValueError("At least one preset is required")
    unknown = set(presets_to_use) - presets.keys()
    if unknown:
        raise ValueError(f"Unknown preset(s): {', '.join(sorted(unknown))}")
    if mode not in ("pad", "crop"):
        raise ValueError("mode must be pad or crop")
    if crf < 0 or crf > 51:
        raise ValueError("CRF must be between 0 and 51")
    if workers not in range(1, 5):
        raise ValueError("Workers must be between 1 and 4")
    srcs = find_videos(input_path, recursive, excluded_folder=output_path)
    if not srcs:
        raise ValueError(f"No supported video files found in {input_path}")
    output_path.mkdir(parents=True, exist_ok=True)
    settings = {"input": str(input_path.resolve()), "output": str(output_path.resolve()),
                "presets": presets_to_use, "preset_definitions": {n: presets[n] for n in presets_to_use},
                "mode": mode, "crf": crf, "workers": workers, "overwrite": overwrite,
                "thumbnails": thumbs, "checksums": checksum}
    if progress:
        progress(f"Found {len(srcs)} source video(s). Producing: {', '.join(presets_to_use)}")
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {
            pool.submit(build_one, src, output_path, presets_to_use, presets, mode, crf,
                        overwrite, thumbs, checksum): src for src in srcs
        }
        for index, future in enumerate(as_completed(jobs), 1):
            row = future.result()
            results.append(row)
            if progress:
                progress(f"[{index}/{len(srcs)}] {jobs[future].name} : {row['status']}")
    results.sort(key=lambda row: row["source"].lower())
    manifest = write_report(output_path, results, settings)
    return {"manifest": str(manifest), "total": len(results),
            "ok": sum(r["status"] == "ok" for r in results),
            "warnings": sum(r["status"] == "warning" for r in results),
            "errors": sum(r["status"] == "error" for r in results)}


def verify(manifest_file: Path) -> dict:
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    problems = []
    checked = 0
    for rec in payload.get("records", []):
        for item in rec.get("outputs", []):
            if item.get("result") == "error":
                problems.append(f"Render failed: {item.get('path')}")
                continue
            path = Path(item["path"])
            checked += 1
            if not path.is_file():
                problems.append(f"Missing: {path}")
                continue
            try:
                actual = probe_media(path)
                expected = item.get("info") or {}
                if actual.width != expected.get("width") or actual.height != expected.get("height"):
                    problems.append(f"Dimensions changed: {path}")
                if abs(actual.duration - expected.get("duration", 0)) > 0.6:
                    problems.append(f"Duration changed: {path}")
            except Exception as exc:
                problems.append(f"Cannot inspect {path}: {exc}")
    return {"checked": checked, "issues": problems, "passed": not problems}
