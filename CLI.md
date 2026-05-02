# MusRen CLI - Documentación

## Introducción

MusRen es una herramienta de línea de comandos para gestionar archivos de música:
- Renombrar archivos basándose en metadatos
- Buscar y embeber letras sincronizadas
- Añadir portadas de álbum
- Reconocimiento de audio via AcoustID/Shazam
- Organizar archivos en carpetas por álbum

## Uso Básico

```bash
# Modo interactivo (por defecto)
python app.py

# Modo comando único
python app.py config list
python app.py rename -d ./musica -y
```

## Modo Interactivo

Al ejecutar `python app.py` sin argumentos, abre una shell interactiva:

```
----------------------------------- MusRen CLI ----------------------------------
Version 1.0.0

+--------------------------------+ MusRen ----------------------------------+
| Welcome to MusRen CLI!                                                      |
|                                                                             |
| Type /help for commands                                                     |
| Type <command> to run                                                       |
+-----------------------------------------------------------------------------+
+----------------------- Commands -----------------------+
|   rename       Rename audio files based on metadata    |
|   lyrics       Search and embed synchronized lyrics    |
|   covers       Add album covers to audio files       |
|   recognize    Recognize audio files using AcoustID   |
|   albums       Organize audio files into album folders |
|   config       Manage configuration and API keys      |
+-----------------------+------------------- ---------------+
...
MusRen Z:\_projects\hobbie\python\MusRen$
```

### Comandos de Navegación

| Comando | Descripción |
|---------|-------------|
| `/help` | Mostrar comandos disponibles |
| `/clear` | Limpiar terminal |
| `/cd <dir>` | Cambiar directorio de trabajo |
| `/pwd` | Mostrar directorio actual |
| `/exit` | Salir de la shell |

## Commands

### config - Configuration Management

Manage API keys and settings.

```bash
# Interactive shell
config set acoustid YOUR_API_KEY
config get acoustid
config list
config delete acoustid
config clear

# Single command mode
python app.py config set acoustid YOUR_API_KEY
python app.py config list
```

**Available keys:**
- `acoustid` - AcoustID API key for audio recognition
- `shazam` - Shazam API credentials (future)
- `musicbrainz` - MusicBrainz credentials (future)
- `lastfm` - Last.fm API key (future)

### rename - Rename Audio Files

Rename audio files based on their metadata (artist - title).

```bash
# Interactive shell
rename -d ./music
rename -d ./music -y
rename -r -d ./music -y

# Single command mode
python app.py rename -d ./music
python app.py rename -d ./music -y
python app.py rename -d ./music --recursive -y
```

**Options:**
- `-d, --directory` - Directory containing audio files (default: current)
- `-R, --recursive` - Search in subdirectories
- `-y, --yes` - Auto-confirm without asking

### lyrics - Search and Embed Lyrics

Search and embed synchronized lyrics to audio files.

```bash
# Interactive shell
lyrics -d ./music
lyrics -d ./music -r
lyrics -d ./music -r -c -y

# Single command mode
python app.py lyrics -d ./music
python app.py lyrics -d ./music --recognition
python app.py lyrics -d ./music --recognition --covers --yes
```

**Options:**
- `-d, --directory` - Directory containing audio files
- `-r, --recognition` - Use audio recognition before searching lyrics
- `-c, --covers` - Also fetch album covers
- `-y, --yes` - Auto-confirm without asking

### covers - Add Album Covers

Add album covers to audio files.

```bash
# Interactive shell
covers -d ./music
covers -d ./music -R -y

# Single command mode
python app.py covers -d ./music
python app.py covers -d ./music --recursive --yes
```

**Options:**
- `-d, --directory` - Directory containing audio files
- `-R, --recursive` - Search in subdirectories
- `-y, --yes` - Auto-confirm without asking

### recognize - Audio Recognition

Recognize audio files using AcoustID or Shazam.

```bash
# Interactive shell
recognize -d ./music
recognize -d ./music -s

# Single command mode
python app.py recognize -d ./music
python app.py recognize -d ./music --shazam
```

**Options:**
- `-d, --directory` - Directory containing audio files
- `-s, --shazam` - Use Shazam instead of AcoustID

### albums - Organize by Albums

Organize audio files into album folders.

```bash
# Interactive shell
albums -d ./music
albums -d ./music -R -y

# Single command mode
python app.py albums -d ./music
python app.py albums -d ./music --recursive --yes
```

**Options:**
- `-d, --directory` - Directory containing audio files
- `-R, --recursive` - Search in subdirectories
- `-y, --yes` - Auto-confirm without asking

## Theme System

The CLI uses Rich for terminal rendering with the following color scheme:

- **Primary**: Cyan (#00B4D8)
- **Secondary**: Magenta (#E91E63)
- **Success**: Green (#4CAF50)
- **Warning**: Yellow (#FFC107)
- **Error**: Red (#F44336)

## Configuration Storage

API keys are stored in `~/.musren/config.json`:

```json
{
  "keys": {
    "acoustid": "YOUR_API_KEY"
  }
}
```

## Legacy Mode

To use the old single-command mode without the interactive shell:

```bash
python app.py --no-interactive -d ./music rename
```

Or directly use the Typer app:

```bash
python -m core.cli.app rename -d ./music
```

## Architecture

```
core/cli/
├── __init__.py           # Exports
├── app.py                # Typer app definition
├── shell.py             # Interactive shell
├── theme.py             # Theming system
├── config.py            # Configuration manager
└── commands/
    ├── __init__.py
    ├── base.py          # Command base class
    ├── config.py       # Config Typer commands
    ├── config_shell.py # Shell-optimized config
    ├── rename.py       # Rename command
    ├── lyrics.py      # Lyrics command
    ├── covers.py      # Covers command
    ├── recognize.py   # Recognize command
    └── albums.py     # Albums command
```

## Dependencies

- `typer` - CLI framework
- `rich` - Terminal rendering
- `mutagen` - Audio metadata
- `requests` - HTTP requests
- `syncedlyrics` - Lyrics fetching

Optional:
- `pyacoustid` - AcoustID recognition
- `musicbrainzngs` - MusicBrainz API