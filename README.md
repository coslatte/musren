# MusRen (Music Renamer)

MusRen is a Python CLI tool to organize your local music library by:

- Renaming files using metadata (artist/title/album/track, etc.)
- Optionally recognizing tracks (AcoustID + Chromaprint `fpcalc`, or Shazam)
- Optionally fetching and embedding album artwork
- Optionally fetching and embedding synchronized lyrics (LRC)

It is designed to be used on folders of audio files (MP3, FLAC, M4A).

## How it works

1. Scans a directory (optionally recursively) for audio files.
2. Reads existing metadata.
3. Optionally recognizes the track and enriches metadata.
4. Optionally embeds lyrics and/or cover art.
5. Renames files based on the resulting metadata.

## Requirements

- Python 3.9+ (recommended)
- Optional for AcoustID recognition: Chromaprint `fpcalc`

### Chromaprint (`fpcalc`) for recognition

AcoustID recognition requires the `fpcalc` binary.

- Windows: download `fpcalc.exe` from Chromaprint releases and add it to `PATH`.
  - MusRen also checks common local locations (project root and `utils/`) if needed.
- macOS: `brew install chromaprint`
- Linux (Debian/Ubuntu): `sudo apt-get install libchromaprint-tools`

## Installation

MusRen can be used directly from source or installed as an editable package.

### Option A: Using Python + pip

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Install the project (so the `music-renamer` command is available):

```powershell
python -m pip install -e .
```

### Option B: Using uv

Create and activate an environment (uv manages the venv for you):

Install dependencies:

```powershell
uv sync
```

Install the project (editable):

```powershell
uv pip install -e .
```

### Optional extras

Some features may require optional dependencies. You can install them via extras:

```powershell
# AcoustID recognition
python -m pip install -e ".[recognition]"

# Synchronized lyrics
python -m pip install -e ".[lyrics]"

# MusicBrainz support (improved lookup)
python -m pip install -e ".[musicbrainz]"
```

With uv:

```powershell
uv pip install -e ".[recognition]"
uv pip install -e ".[lyrics]"
uv pip install -e ".[musicbrainz]"
```

## Configuration

### AcoustID API key

You can pass an API key with `--api-key/-k` or set it via environment variable:

```powershell
$env:ACOUSTID_API_KEY="your_key_here"
```

## Usage

MusRen uses a Typer-based CLI.

Show help:

```powershell
python app.py --help
```

If installed, you can also use:

```powershell
music-renamer --help
```

### Common commands

Process the current folder (interactive prompts):

```powershell
python app.py
```

Pick a directory:

```powershell
python app.py -d "D:\Music"
```

Scan subfolders:

```powershell
python app.py -d "D:\Music" -R
```

Fetch and embed synchronized lyrics:

```powershell
python app.py -d "D:\Music" -l
```

Add album covers:

```powershell
python app.py -d "D:\Music" -c
```

Use recognition with AcoustID (requires `fpcalc`):

```powershell
python app.py -d "D:\Music" -r -k "YOUR_ACOUSTID_KEY"
```

Use Shazam instead of AcoustID (Recommended):

```powershell
python app.py -d "D:\Music" -s
```

Run without confirmations:

```powershell
python app.py -d "D:\Music" -y
```

## Project layout

Key files and folders:

```dir
app.py                  # main entrypoint (Typer)
core/                   # processing logic
    audio_processor.py    # rename/metadata/lyrics/covers orchestration
    artwork.py            # cover art fetch + embed
    install_covers.py     # cover-install helper
    shazam_processor.py   # optional Shazam integration
utils/                  # helpers (dependency checks, filesystem tools)
tests/                  # lightweight tests
```

## Troubleshooting

- Recognition fails / `fpcalc` missing: install Chromaprint and ensure `fpcalc` is in `PATH`.
- Optional-feature import errors (lyrics/recognition/musicbrainz): install the matching extras.

## Tests

With pip:

```powershell
python -m pytest -q
```

With uv:

```powershell
uv run pytest -q
```

## Type checking (optional)

This repo includes a Pyright configuration in `pyproject.toml`. To run it:

```powershell
python -m pip install pyright
pyright
```
