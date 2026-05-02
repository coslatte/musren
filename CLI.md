# musren CLI - Documentación

## Introducción

musren es una herramienta de línea de comandos para gestionar archivos de música:
- Renombrar archivos basándose en metadatos
- Buscar y embeber letras sincronizadas
- Añadir portadas de álbum
- Reconocimiento de audio via AcoustID/Shazam
- Organizar archivos en carpetas por álbum

## Instalación

```bash
# Instalación básica
pip install musren

# Con todas las funcionalidades
pip install musren[recognition,lyrics]

# Desarrollo
git clone https://github.com/coslatte/musren.git
cd musren
pip install -e .
```

## Uso

### Modo Interactivo

```bash
musren
```

Muestra un menú interactivo donde puedes:
- Escribir números (1-7) para seleccionar comandos
- Escribir comandos directamente
- Usar /help, /clear, /cd, /pwd, /exit

### Comandos de Línea

```bash
# Configuración
musren config list
musren config set acoustid TU_API_KEY
musren config get acoustid

# Renombrar archivos
musren rename -d ./musica
musren rename -d ./musica -y

# Letras
musren lyrics -d ./musica
musren lyrics -d ./musica -r -c

# Portadas
musren covers -d ./musica
musren covers -d ./musica -R

# Reconocimiento
musren recognize -d ./musica

# Organizar por álbumes
musren albums -d ./musica
```

## Opciones Comunes

| Opción | Descripción |
|--------|-------------|
| `-d, --directory` | Directorio de trabajo |
| `-R, --recursive` | Buscar en subdirectorios |
| `-y, --yes` | Auto-confirmar sin preguntar |

## API Keys

### AcoustID
1. Registrate en https://acoustid.org/
2. Obtén tu API key
3. Configura: `musren config set acoustid TU_KEY`

## Configuración

Las API keys se almacenan en `~/.musren/config.json`:

```json
{
  "keys": {
    "acoustid": "TU_API_KEY"
  }
}
```

## Desarrollo

```bash
# Build
pip install build
python -m build

# Install local
pip install dist/musren-*.whl

# Tests
pytest -q
```

## Estructura del Proyecto

```
musren/
├── core/cli/           # CLI interactivo
│   ├── shell.py       # Shell principal
│   ├── commands/      # Comandos
│   └── theme.py       # Sistema de temas
├── constants/          # Constantes
├── utils/             # Utilidades
├── tests/             # Tests
└── setup.py           # Configuración
```

## Licencia

MIT License - Ver LICENSE