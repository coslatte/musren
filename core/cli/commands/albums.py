import shutil
from collections import defaultdict
from pathlib import Path

import typer
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from core.cli.config import get_config_manager
from core.cli.theme import theme
from utils.tools import get_audio_files

albums_app = typer.Typer(help="Organize audio files into album folders")


@albums_app.command("run")
def albums_run(
    directory: Path = typer.Option(
        Path.cwd(),
        "--directory",
        "-d",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Directory containing audio files",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-R",
        help="Search files in subdirectories",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Execute without confirmations",
    ),
) -> None:
    """Organize audio files into album folders."""
    audio_dir = str(directory)
    files = get_audio_files(audio_dir, recursive=recursive)

    if not files:
        typer.echo(
            Panel(
                f"No audio files found in '{directory}'",
                border_style="yellow",
                title="Warning",
            )
        )
        return

    table = Table(title="Configuration", box="simple_heavy")
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Directory", str(directory))
    table.add_row("Recursive", "Yes" if recursive else "No")
    table.add_row("Files found", str(len(files)))
    typer.echo(table)

    album_groups: dict[str, list[Path]] = defaultdict(list)

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=None, complete_style="cyan", finished_style="green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        expand=True,
    ) as progress:
        task_id = progress.add_task("Analyzing albums...", total=len(files))

        for file_path in files:
            file_path = Path(file_path)
            try:
                from mutagen._file import File as MutagenFile

                audio = MutagenFile(file_path, easy=True)
                album = "Unknown Album"

                if audio:
                    album_tags = audio.get("album", [])
                    if album_tags:
                        album = album_tags[0] if album_tags[0] else "Unknown Album"
            except Exception:
                album = "Unknown Album"

            album_groups[album].append(file_path)

            filename = file_path.name
            if len(filename) > 40:
                filename = filename[:37] + "..."

            progress.update(
                task_id,
                advance=1,
                description=f"Analyzing: [bold white]{filename}[/bold white]",
            )

    singles_dir = directory / "Singles"
    singles_dir.mkdir(exist_ok=True)

    albums_moved = 0
    singles_count = 0
    errors = []

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=None, complete_style="cyan", finished_style="green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        expand=True,
    ) as progress:
        total_moves = sum(len(tracks) for tracks in album_groups.values())
        task_id = progress.add_task("Organizing...", total=total_moves)

        for album, tracks in album_groups.items():
            if album != "Unknown Album":
                safe_album = "".join(
                    c for c in album if c.isalnum() or c in (" ", "-", "_")
                ).rstrip()
                if not safe_album:
                    safe_album = "Unknown Album"
                album_dir = directory / safe_album
                album_dir.mkdir(exist_ok=True)

                for track in tracks:
                    try:
                        dest_path = album_dir / track.name
                        shutil.move(str(track), str(dest_path))
                        albums_moved += 1
                    except Exception as e:
                        errors.append(f"{track.name}: {e}")

                    progress.update(
                        task_id,
                        advance=1,
                        description=f"Moving: [bold white]{track.name}[/bold white]",
                    )
            else:
                for track in tracks:
                    try:
                        dest_path = singles_dir / track.name
                        shutil.move(str(track), str(dest_path))
                        singles_count += 1
                    except Exception as e:
                        errors.append(f"{track.name}: {e}")

                    progress.update(
                        task_id,
                        advance=1,
                        description=f"Moving: [bold white]{track.name}[/bold white]",
                    )

    stats_table = Table(title="Organization Summary", box="simple")
    stats_table.add_column("Metric", style="bold cyan")
    stats_table.add_column("Value", style="white")
    stats_table.add_row("Albums created", str(len([a for a in album_groups.keys() if a != "Unknown Album"])))
    stats_table.add_row("Tracks in albums", str(albums_moved))
    stats_table.add_row("Tracks in Singles", str(singles_count))
    stats_table.add_row("Errors", str(len(errors)))
    typer.echo(stats_table)

    if errors:
        error_table = Table(title="Errors", box="simple")
        error_table.add_column("File", style="bold red")
        error_table.add_column("Error", style="red")
        for error in errors:
            parts = error.split(": ", 1)
            error_table.add_row(parts[0], parts[1] if len(parts) > 1 else "Unknown")
        typer.echo(error_table)

    typer.echo(
        Panel(
            "Files organized successfully.",
            border_style="green",
            title="Completed",
        )
    )