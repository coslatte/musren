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

### Option A: One-click install scripts (recommended)

```powershell
# Windows
.\install.ps1

# Or build + install manually
.\build.bat
```

```bash
# Linux/Mac
./install.sh
```

### Option B: Manual

```powershell
# Build wheel
python -m build

# Install
pip install dist/musren-1.1.0-py3-none-any.whl
```

### Option C: Editable (development)

```powershell
pip install -e .
```

Some features may require optional dependencies:

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

MusRen provides an interactive CLI and command-line mode.

### Interactive mode

```powershell
musren
```

Shows a menu with options 1-7 for rename, lyrics, covers, recognize, albums, config, help.

### Command-line mode

Run a command directly:

```powershell
musren rename
musren lyrics
musren covers
```

### Version check

```powershell
musren --version
```

### Legacy mode (direct Python)

```powershell
python app.py --help
```

## Project layout

Key files and folders:

```
app.py                  # main entrypoint
core/                   # processing logic
core/cli/               # CLI (shell interface)
core/cli/commands/      # menu commands
constants/            # settings and version
utils/                 # helpers
tests/                 # tests
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
