# CLI reference

`musren` opens the original interactive menu. `musren COMMAND` runs a CLI
operation. For the portable Windows build, replace `musren` with
`.\musren-windows-x64.exe`; use `--cli` to open the original menu.

## Commands

| Command | Behavior |
| --- | --- |
| `rename` | Rename audio files from their existing metadata |
| `lyrics` | Fetch and embed synchronized lyrics |
| `covers` | Fetch artwork and embed it in files without covers |
| `recognize` | Recognize tracks and update metadata |
| `albums` | Group album tracks and singles into folders |
| `albums revert` | Move audio files from subfolders to the chosen root |
| `config` | Manage saved API credentials |

`--help` displays available commands or options. `--version` prints the installed
version. The explicit `run` subcommand also works, such as `musren rename run`.

## Audio options

| Flag | Meaning |
| --- | --- |
| `--directory PATH`, `-d PATH` | Directory to process; defaults to the current directory |
| `--recursive`, `-R` | Include subdirectories; album revert always scans subdirectories |
| `--yes`, `-y` | Skip command confirmations |

### Rename

| Flag | Meaning |
| --- | --- |
| `--format 1` | `Artist - Title` |
| `--format 2` | `Title` |
| `--format 3` | `Track - Artist - Title` for an album; otherwise artist and title |

Track numbers apply when at least three tracks share an album. Without `--format`,
rename prompts for a format. With `--yes`, the default is format 1. A completed
interactive rename asks whether to keep or undo its changes.

```shell
musren rename --directory "Music collection" --format 2
musren rename --directory "Music collection" --recursive --format 3 --yes
```

### Lyrics

| Flag | Meaning |
| --- | --- |
| `--recognition`, `-r` | Recognize tracks before searching for lyrics |
| `--covers`, `-c` | Also fetch artwork |

```shell
musren lyrics --directory "Music collection" --recursive
musren lyrics --directory "Music collection" --recognition --covers
```

### Recognition

`--shazam`, or `-s`, selects Shazam. The default backend is AcoustID, which
requires an API key and `fpcalc` in PATH.

```shell
musren recognize --directory "Music collection"
musren recognize --directory "Music collection" --shazam
```

### Albums

Organization puts album groups into folders and singleton tracks into Singles.
Organization and revert preserve existing files when names collide.

```shell
musren albums --directory "Music collection" --recursive
musren albums revert --directory "Music collection"
```

## Configuration

Credentials are stored in `~/.musren/config.json`. AcoustID is the active key
used by the recognition engine. Other accepted key names reserve service
configuration for `shazam`, `musicbrainz`, and `lastfm`.

```shell
musren config set acoustid YOUR_KEY
musren config get acoustid
musren config list
musren config delete acoustid
musren config clear
```

The CLI's `get` and `list` commands print saved credentials. `clear` asks before
removing all configuration. The TUI displays credential status and masked inputs.

## Original menu

The menu accepts operation numbers or command names. `/help`, `/clear`, `/cd`,
`/pwd`, and `/exit` provide shell navigation. `b` returns to the main menu.

See [the terminal interface guide](tui.md) for the TUI and
[the README](../README.md) for installation and dependency requirements.
