from pathlib import Path
from typing import Optional

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

from core.audio_processor import AudioProcessor
from core.cli.config import get_config_manager
from core.cli.theme import theme
from utils.dependencies import check_dependencies
from utils.tools import get_audio_files

console = theme.styles

rename_app = typer.Typer(help="Rename audio files based on metadata")


@rename_app.command("run")
def rename_run(
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
    """Rename audio files based on their metadata."""
    if not check_dependencies(use_recognition=False):
        typer.echo(
            Panel(
                "Missing dependencies. Aborting...",
                border_style="red",
                title="Error",
            )
        )
        raise typer.Exit(1)

    config = get_config_manager()
    api_key = config.get("acoustid")

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

    processor = AudioProcessor(
        directory=audio_dir,
        acoustid_api_key=api_key,
        recursive=recursive,
    )

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=None, complete_style="cyan", finished_style="green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        expand=True,
    ) as progress:
        task_id = progress.add_task("Renaming...", total=len(files))

        def rename_callback(file_path, result):
            filename = Path(file_path).name
            if len(filename) > 40:
                filename = filename[:37] + "..."

            status = ""
            if result.get("renamed"):
                status = "[green]Renamed[/green]"
            elif result.get("skipped"):
                status = "[dim]Skipped[/dim]"
            elif result.get("error"):
                status = "[red]Error[/red]"
            else:
                status = "[dim]No changes[/dim]"

            progress.update(
                task_id,
                advance=1,
                description=f"Renaming: [bold white]{filename}[/bold white] - {status}",
            )

        changes = processor.rename_files(progress_callback=rename_callback)

    if changes:
        changes_table = Table(title="Name changes", box="simple_heavy")
        changes_table.add_column("Before", style="yellow")
        changes_table.add_column("After", style="green")
        for new_path, old_path in changes.items():
            changes_table.add_row(Path(old_path).name, Path(new_path).name)
        typer.echo(changes_table)

        keep_changes = yes or typer.confirm("Do you want to keep the name changes?")
        if not keep_changes:
            with Progress(
                SpinnerColumn(style="bold yellow"),
                TextColumn("[bold yellow]{task.description}"),
                BarColumn(
                    bar_width=None, complete_style="yellow", finished_style="green"
                ),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                expand=True,
            ) as progress:
                task_id = progress.add_task("Reverting...", total=len(changes))

                def undo_callback(file_path, result):
                    filename = Path(file_path).name
                    if len(filename) > 40:
                        filename = filename[:37] + "..."
                    progress.update(
                        task_id,
                        advance=1,
                        description=f"Reverting: [bold white]{filename}[/bold white]",
                    )

                processor.undo_rename(changes, progress_callback=undo_callback)

            typer.echo(
                Panel(
                    "The name changes have been reverted.",
                    border_style="yellow",
                    title="Reverted",
                )
            )
        else:
            typer.echo(
                Panel(
                    "The name changes have been kept.",
                    border_style="green",
                    title="Ready",
                )
            )
    else:
        typer.echo("[bold]No name changes were made.[/bold]")

    typer.echo(
        Panel(
            "Process completed successfully.",
            border_style="green",
            title="Completed",
        )
    )