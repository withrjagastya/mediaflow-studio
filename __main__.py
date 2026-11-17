"""CLI: python -m mediaflow [doctor|scan|build|verify]."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .core import find_videos, probe_media, DEFAULT_PRESETS
from .pipeline import build, verify


def parser_for_cli():
    parser = argparse.ArgumentParser(prog="mediaflow", description="Offline, multi-format video workflow using FFmpeg")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor", help="Check FFmpeg and FFprobe installation")
    scan = subs.add_parser("scan", help="Inspect videos without modifying them")
    scan.add_argument("--input", required=True, type=Path)
    scan.add_argument("--no-recursive", action="store_true")
    render = subs.add_parser("build", help="Create videos, thumbnails, and QC reports")
    render.add_argument("--input", required=True, type=Path)
    render.add_argument("--output", required=True, type=Path)
    render.add_argument("--presets", nargs="+", default=["reel", "square", "landscape"])
    render.add_argument("--preset-file", type=Path, help="Custom presets JSON")
    render.add_argument("--mode", choices=["pad", "crop"], default="pad")
    render.add_argument("--crf", type=int, default=24, help="Quality: lower is better (0-51)")
    render.add_argument("--workers", type=int, default=1, help="Parallel jobs (1-4)")
    render.add_argument("--overwrite", action="store_true")
    render.add_argument("--no-thumbnails", action="store_true")
    render.add_argument("--checksum", action="store_true")
    render.add_argument("--no-recursive", action="store_true")
    validate = subs.add_parser("verify", help="Check exported files against the JSON report")
    validate.add_argument("--report", required=True, type=Path)
    subs.add_parser("presets", help="List built-in output formats")
    return parser


def main(argv=None):
    args = parser_for_cli().parse_args(argv)
    try:
        if args.command == "doctor":
            for tool in ("ffmpeg", "ffprobe"):
                print(f"{tool}: {shutil.which(tool) or 'NOT FOUND'}")
            return 0 if all(shutil.which(s) for s in ("ffmpeg", "ffprobe")) else 1
        if args.command == "presets":
            print(json.dumps(DEFAULT_PRESETS, indent=2))
            return 0
        if args.command == "scan":
            paths = find_videos(args.input, not args.no_recursive)
            rows = []
            for path in paths:
                try:
                    rows.append(probe_media(path).to_dict())
                except Exception as exc:
                    rows.append({"path": str(path), "error": str(exc)})
            print(json.dumps(rows, indent=2, ensure_ascii=False))
            return 0 if rows else 1
        if args.command == "build":
            result = build(args.input, args.output, args.presets, args.mode, args.crf,
                           args.workers, args.overwrite, not args.no_thumbnails,
                           args.checksum, args.preset_file, not args.no_recursive, progress=print)
            print(json.dumps(result, indent=2))
            return 1 if result["errors"] else 0
        if args.command == "verify":
            result = verify(args.report)
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 1
    except (ValueError, FileNotFoundError, NotADirectoryError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
