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
from utils.dependencies import check_dependencies
from utils.tools import get_audio_files

covers_app = typer.Typer(help="Add album covers to audio files")


@covers_app.command("run")
def covers_run(
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
    """Add album covers to audio files."""
    if not check_dependencies(use_recognition=False):
        typer.echo(
            Panel(
                "Missing dependencies. Aborting...",
                border_style="red",
                title="Error",
            )
        )
        raise typer.Exit(1)

    # Lazy import to avoid loading module if not installed
    try:
        import core.install_covers as install_covers
    except ImportError:
        typer.echo(
            Panel(
                "Could not import the cover installation module.",
                border_style="red",
                title="Error",
            )
        )
        raise typer.Exit(1)

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

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=None, complete_style="cyan", finished_style="green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        expand=True,
    ) as progress:
        task_id = progress.add_task("Adding covers...", total=len(files))

        def progress_callback(file_path: str, result: dict) -> None:
            filename = Path(file_path).name
            if len(filename) > 40:
                filename = filename[:37] + "..."

            status = ""
            if not result.get("status"):
                status = "[red]Error[/red]"
            elif result.get("skipped"):
                status = "[yellow]Skipped[/yellow]"
            else:
                status = "[green]Added[/green]"

            progress.update(
                task_id,
                advance=1,
                description=f"Processing: [bold white]{filename}[/bold white] - {status}",
            )

        install_covers.run(audio_dir, progress_callback=progress_callback)

    typer.echo(
        Panel(
            "Covers added successfully.",
            border_style="green",
            title="Completed",
        )
    )