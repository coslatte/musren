# musren (Music Renamer)

musren is a Python CLI tool to organize your local music library.

## Quick Install

```powershell
# Windows
.\install.ps1

# Or build manually
python -m build
pip install dist/musren-*.whl
```

```bash
# Linux/Mac
./install.sh
```

## What is musren?

musren organizes your music by:

- **Rename** files using metadata (artist/title/album/track)
- **Recognize** tracks via AcoustID or Shazam
- **Embed** album artwork and synchronized lyrics (LRC)
- **Organize** files into album folders

## How it works

1. Scans a directory (optionally recursive) for audio files
2. Reads existing metadata
3. Optionally recognizes and enriches metadata
4. Optionally embeds lyrics and/or cover art
5. Renames files based on the metadata

## Requirements

- Python 3.9+
- Optional for recognition: Chromaprint `fpcalc`

### Install fpcalc (for AcoustID)

- Windows: download `fpcalc.exe` from Chromaprint releases
- macOS: `brew install chromaprint`
- Linux: `sudo apt-get install libchromaprint-tools`

## Usage

```powershell
# Interactive mode
python app.py

# Or install as command
pip install -e .
musren
```

### Interactive Menu

Run `python app.py` and select:
- 1. Rename - rename files based on metadata
- 2. Lyrics - fetch and embed lyrics
- 3. Covers - add album artwork
- 4. Recognize - audio recognition
- 5. Albums - organize by folders
- 6. Config - API key settings
- 7. Help - show guide

### Command-line mode

```powershell
musren rename --directory C:\Music
musren lyrics --directory C:\Music -R
musren covers --directory C:\Music
```

### Version

```powershell
musren --version
```

## Configuration

Set AcoustID API key:

```powershell
$env:ACOUSTID_API_KEY="your_key"
# or in musren shell:
config set acoustid YOUR_KEY
```

## Optional Features

```powershell
pip install -e ".[recognition]"  # AcoustID
pip install -e ".[lyrics]"       # Lyrics
pip install -e ".[musicbrainz]"  # MusicBrainz
```

## Tests

```powershell
python -m pytest -q
```

## Troubleshooting

- Recognition fails: install Chromaprint and ensure `fpcalc` is in PATH
- Import errors: install matching extras (`.[recognition]`, `.[lyrics]`, etc.)