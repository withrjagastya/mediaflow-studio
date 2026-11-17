# MediaFlow Studio 🎬

**An open-source, offline video production pipeline for independent creators.**

Turn a folder of raw videos into multiple social-media delivery formats, thumbnails, and a quality-control report — with one command or a simple desktop GUI. No uploads, accounts, server, tokens, or cloud API.

## Why this project exists

Video editors often repeat tedious export and checking tasks for every social platform. MediaFlow automates that workflow, making format conversion, metadata inspection, and delivery validation reproducible. It is an automation tool, **not an AI video editor or automatic transcription service**.

## Features

- **Multiple export presets:** 9:16 vertical Reel/Short, square, 16:9 landscape and lightweight preview.
- **Framing control:** letterbox/pad to preserve the whole shot or center-crop to fill the frame.
- **Batch processing:** scan directories recursively and safely handle matching file names.
- **Thumbnails:** JPEG preview frame for each original video.
- **QC:** uses FFprobe to compare exported dimensions and durations; `verify` can re-check later.
- **Reports:** machine-readable JSON manifest and spreadsheet-friendly UTF-8 CSV.
- **Resumable:** existing exports are reused unless you choose `--overwrite`.
- **Optional SHA-256 checksums** for source files.
- **CLI and desktop GUI:** Python standard library for code; FFmpeg for video processing.
- **GitHub Actions:** automated unit and integration tests for new changes.

## Setup (Windows)

1. Install **Python 3.10+** from https://www.python.org/downloads/ (enable "Add Python to PATH").
2. Install **FFmpeg**, including `ffprobe`, from https://ffmpeg.org/download.html and make sure `ffmpeg` and `ffprobe` work in Command Prompt.
3. Download/clone the repository. Open **Command Prompt** in the repository folder.
4. Check dependencies:

```powershell
python -m mediaflow doctor
```

You do **not** need to run `pip install` to use the project from its source directory. On Windows you can also double-click **`START_ON_WINDOWS.bat`** after Python and FFmpeg are installed.

## Desktop app (recommended for beginners)

```powershell
python -m mediaflow.gui
```

Choose a source folder, an export folder, formats and framing mode, then press **Build videos**. MediaFlow does not modify source files.

## CLI usage

First make a folder named `input` containing 1 or more videos. Then:

```powershell
python -m mediaflow scan --input input
python -m mediaflow build --input input --output output --presets reel square landscape --mode pad
python -m mediaflow verify --report output/mediaflow-report.json
```

**Other options:**

```powershell
python -m mediaflow build --input input --output output --presets reel preview --mode crop --crf 22 --workers 2 --checksum
python -m mediaflow build --input input --output output --presets shorts_hd wide_hd --preset-file examples/presets.json
python -m mediaflow build --input input --output output --presets reel --overwrite
python -m mediaflow presets
```

- `--mode pad` fits the entire shot within the target frame using black bars where necessary (default).
- `--mode crop` center-crops edges, which can cut off subjects near frame boundaries.
- `--crf` controls H.264 compression: lower = higher visual quality/larger files. Default 24.
- `--workers` processes videos in parallel (1–4), increasing CPU/RAM demand.
- `--no-thumbnails`, `--no-recursive`, `--checksum`, `--overwrite` are available.
- On an interrupted job, rerun the same command. Completed exports will be skipped.

## Sample output structure

```text
output/
├── videos/
│   ├── reel/clip-a1b2c3d4-reel.mp4
│   ├── square/clip-a1b2c3d4-square.mp4
│   └── landscape/clip-a1b2c3d4-landscape.mp4
├── thumbnails/clip-a1b2c3d4.jpg
├── mediaflow-report.json
└── mediaflow-report.csv
```

## Custom presets

Create a JSON file like `examples/presets.json`. Preset names must use letters, digits, dashes or underscores; widths and heights must be even pixel counts from 2 to 4096. Call `--preset-file` to use it.

## Automated tests

```powershell
python -m unittest discover -s tests -v
```

Tests use a tiny synthetic video generated locally by FFmpeg. The GitHub Action runs these tests on pushes and pull requests.

## Known limitations / roadmap

- Exports always re-encode with H.264/AAC and can take time for large 4K files.
- Framing is center-based; no smart subject tracking or AI reframing.
- Image thumbnails use an existing frame, not automatic best-frame analysis.
- Custom text/subtitle overlays, GUI preview and asynchronous job cancellation are future improvements.
- Some unusual media streams/codecs may need manual FFmpeg adjustments.
- Current GUI's Stop button stops the controller; the active FFmpeg encode may continue briefly.

## Contributing

Issues and pull requests for bug fixes, localization, new presets, and processing improvements are welcome. Please include before/after output dimensions, a reproducible sample command, and (when possible) automated tests. Never upload copyrighted footage without permission or include private client material in an issue.

## Privacy

All processing happens on the local computer. No personal media is sent to a hosted service. The report contains **absolute local file paths**, so review or redact it before sharing publicly. Git ignores `input/`, `output/` and `exports/` by default.

## License

MIT license. See [LICENSE](LICENSE).
