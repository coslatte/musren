import os
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from dotenv import load_dotenv
from rich import box
from rich.console import Console
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
from rich.traceback import install as rich_traceback_install

from constants.info import PARSER_DESCRIPTION
from core.audio_processor import AudioProcessor
from utils.dependencies import check_dependencies
from utils.tools import get_audio_files

load_dotenv()
rich_traceback_install(show_locals=False)

app = typer.Typer(help=PARSER_DESCRIPTION)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    directory: Path = typer.Option(
        Path.cwd(),
        "--directory",
        "-d",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Directorio de los archivos, de no especificarse se utiliza el actual",
    ),
    recursive: bool = typer.Option(
        False, "--recursive", "-R", help="Buscar archivos en subdirectorios"
    ),
    lyrics: bool = typer.Option(
        False, "--lyrics", "-l", help="Buscar e incrustar letras sincronizadas"
    ),
    recognition: bool = typer.Option(
        False, "--recognition", "-r", help="Usar reconocimiento de audio con AcoustID"
    ),
    cover: bool = typer.Option(
        False, "--covers", "-c", help="Añadir portadas de álbum"
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k", help="AcoustID API key (opcional)"
    ),
    shazam: bool = typer.Option(
        False, "--shazam", "-s", help="Usar Shazam en lugar de AcoustID"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Ejecutar todo sin confirmaciones"
    ),
):
    console.rule("[bold cyan]MusRen[/bold cyan]")
    with console.status("Verificando dependencias...", spinner="dots"):
        if not check_dependencies():
            console.print(
                Panel.fit(
                    "Dependencias faltantes. Abortando...",
                    border_style="red",
                    title="Error",
                )
            )
            raise typer.Exit(1)

    opts_table = Table(
        title="Configuración",
        box=box.SIMPLE_HEAVY,
        show_header=False,
        padding=(0, 1),
    )
    opts_table.add_column("Clave", style="bold cyan")
    opts_table.add_column("Valor", style="white")
    opts_table.add_row("Directorio", str(directory))
    opts_table.add_row("Recursivo (-R)", "Sí" if recursive else "No")
    opts_table.add_row("Letras (-l)", "Sí" if lyrics else "No")
    opts_table.add_row("Reconocimiento (-r)", "Sí" if recognition else "No")
    opts_table.add_row("Shazam (-s)", "Sí" if shazam else "No")
    opts_table.add_row("Portadas (-c)", "Sí" if cover else "No")
    opts_table.add_row("Auto-confirmar (-y)", "Sí" if yes else "No")
    console.print(Panel(opts_table, border_style="cyan"))

    if api_key is None:
        api_key = os.getenv("ACOUSTID_API_KEY")

    processor = AudioProcessor(
        directory=str(directory),
        acoustid_api_key=str(api_key) if api_key else os.getenv("ACOUSTID_API_KEY"),
        recursive=recursive,
        use_shazam=shazam,
    )
    with console.status("Buscando archivos de audio...", spinner="line"):
        files = get_audio_files(directory=directory, recursive=recursive)

    if not files:
        console.print(
            Panel.fit(
                "No se encontraron archivos de audio en el directorio seleccionado.",
                border_style="yellow",
                title="Aviso",
            )
        )
        raise typer.Exit(1)

    summary_table = Table(box=box.MINIMAL_DOUBLE_HEAD, show_header=False)
    summary_table.add_column("Item", style="bold green")
    summary_table.add_column("Valor", style="white")
    summary_table.add_row("Archivos encontrados", str(len(files)))
    console.print(summary_table)

    if cover and not (lyrics or recognition):
        console.print(
            Panel.fit(
                "Se utilizará la función de búsqueda e incrustación de portadas de álbum.",
                border_style="magenta",
                title="Portadas",
            )
        )
        try:
            # Usar el procesador principal en lugar de la función legacy add_covers
            # Esto asegura que se respete la recursividad y la lógica centralizada
            stats = process_lyrics_and_stats(
                processor,
                use_recognition=False,
                process_lyrics=False,
                fetch_covers=True,
            )
            console.print("[bold green]Portadas añadidas correctamente.[/bold green]")
        except Exception as e:
            console.print(Panel.fit(str(e), border_style="red", title="Error"))
            raise typer.Exit(1)

    if lyrics or recognition:
        title_text = "Letras"
        if recognition and not lyrics:
            title_text = "Reconocimiento"
        elif recognition and lyrics:
            title_text = "Reconocimiento y Letras"

        console.print(
            Panel.fit(
                f"Se utilizará la función de {title_text}.",
                border_style="magenta",
                title=title_text,
            )
        )

        stats = process_lyrics_and_stats(
            processor,
            use_recognition=recognition,
            process_lyrics=lyrics,
            fetch_covers=cover,
        )

        stats_table = Table(
            title=f"Resumen del procesamiento ({title_text})", box=box.SIMPLE
        )
        stats_table.add_column("Métrica", style="bold cyan")
        stats_table.add_column("Valor", style="white")
        stats_table.add_row("Total de archivos", str(stats.get("total", 0)))
        if recognition:
            stats_table.add_row("Reconocidos", str(stats.get("recognized", 0)))
        if lyrics:
            stats_table.add_row("Letras encontradas", str(stats.get("lyrics_found", 0)))
            stats_table.add_row(
                "Letras incrustadas", str(stats.get("lyrics_embedded", 0))
            )
        console.print(stats_table)

        results = stats.get("results", {}) or {}
        if results:
            detail = Table(title="Detalle por archivo", box=box.SIMPLE_HEAVY)
            detail.add_column("Archivo", style="bold")
            if recognition:
                detail.add_column("Recon.", justify="center")
            detail.add_column("Artista - Título", overflow="fold", style="white")
            if lyrics:
                detail.add_column("Letras", justify="center")
                detail.add_column("Incrustadas", justify="center")
            detail.add_column("Error", style="red")

            def _tick(val: bool) -> str:
                return "[green]✔[/green]" if val else "[red]✖[/red]"

            for file, res in results.items():
                recognized = bool(res.get("recognition", False))
                lyrics_found = bool(res.get("lyrics_found", False))
                embedded = bool(res.get("lyrics_embedded", False))
                artist_title = ""
                if recognized:
                    artist_title = (
                        f"{res.get('artist', '')} - {res.get('title', '')}".strip()
                    )
                if not artist_title:
                    artist_title = os.path.basename(file)

                error_msg = (
                    res.get("embed_error")
                    or res.get("lyrics_error")
                    or res.get("recognition_error")
                    or res.get("metadata_error")
                    or ""
                )

                # Si hubo error de reconocimiento, mostrarlo explícitamente
                if recognition and not recognized and not error_msg:
                    error_msg = "No reconocido (Score bajo o sin coincidencia)"

                row_data = [os.path.basename(file)]
                if recognition:
                    row_data.append(_tick(recognized))

                row_data.append(artist_title)

                if lyrics:
                    row_data.append(_tick(lyrics_found))
                    row_data.append(_tick(embedded))

                row_data.append(error_msg)

                detail.add_row(*row_data)

            console.print(detail)

    proceed_rename = True
    if not yes:
        proceed_rename = typer.confirm("¿Comenzar renombramiento de archivos?")
    else:
        console.print("[bold yellow]Auto-confirmación activada (-y).[/bold yellow]")

    if not proceed_rename:
        console.print(
            Panel.fit(
                "Operación de renombramiento cancelada.",
                border_style="yellow",
                title="Cancelado",
            )
        )
        raise typer.Exit()

    # Contar archivos para la barra de progreso de renombrado
    files_to_rename = get_audio_files(directory, recursive=recursive)

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=None, complete_style="cyan", finished_style="green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=True,
    ) as progress:
        task_id = progress.add_task("Renombrando...", total=len(files_to_rename))

        def rename_callback(file_path, result):
            filename = os.path.basename(file_path)
            if len(filename) > 40:
                filename = filename[:37] + "..."

            status = ""
            if result.get("renamed"):
                status = "[green]Renombrado[/green]"
            elif result.get("skipped"):
                status = "[dim]Saltado[/dim]"
            elif result.get("error"):
                status = "[red]Error[/red]"
            else:
                status = "[dim]Sin cambios[/dim]"

            progress.update(
                task_id,
                advance=1,
                description=f"Renombrando: [bold white]{filename}[/bold white] - {status}",
            )

        changes = processor.rename_files(progress_callback=rename_callback)

    if changes:
        changes_table = Table(title="Cambios de nombre", box=box.SIMPLE_HEAVY)
        changes_table.add_column("Antes", style="yellow")
        changes_table.add_column("Después", style="green")
        for new_path, old_path in changes.items():
            # Mostrar solo el nombre del archivo para que la tabla no sea gigante
            # o mostrar ruta relativa si es recursivo?
            # Mostremos nombre base para legibilidad, pero tooltip/debug tendría full path
            changes_table.add_row(
                os.path.basename(old_path), os.path.basename(new_path)
            )
        console.print(changes_table)

        keep_changes = True
        if not yes:
            keep_changes = typer.confirm("¿Desea mantener los cambios de nombre?")

        if not keep_changes:
            with Progress(
                SpinnerColumn(style="bold yellow"),
                TextColumn("[bold yellow]{task.description}"),
                BarColumn(
                    bar_width=None, complete_style="yellow", finished_style="green"
                ),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console,
                expand=True,
            ) as progress:
                task_id = progress.add_task("Revirtiendo...", total=len(changes))

                def undo_callback(file_path, result):
                    filename = os.path.basename(file_path)
                    if len(filename) > 40:
                        filename = filename[:37] + "..."

                    progress.update(
                        task_id,
                        advance=1,
                        description=f"Revirtiendo: [bold white]{filename}[/bold white]",
                    )

                processor.undo_rename(changes, progress_callback=undo_callback)

            console.print(
                Panel.fit(
                    "Los cambios de nombre se han revertido.",
                    border_style="yellow",
                    title="Revertido",
                )
            )
        else:
            console.print(
                Panel.fit(
                    "Los cambios de nombre se han mantenido.",
                    border_style="green",
                    title="Listo",
                )
            )
    else:
        console.print("[bold]No se realizaron cambios de nombre.[/bold]")

    console.rule("[bold green]Proceso completado[/bold green]")
    console.print(
        Panel.fit(
            "El proceso ha concluido correctamente.",
            border_style="green",
            title="Completado",
        )
    )
    if not yes:
        try:
            try:
                import click

                click.pause(info="Presiona Enter para salir...", err=False)
            except Exception:
                input("Presiona Enter para salir...")
        finally:
            raise typer.Exit(0)


def process_lyrics_and_stats(
    processor,
    use_recognition: bool,
    process_lyrics: bool = True,
    fetch_covers: bool = False,
) -> Dict[str, Any]:
    # Contar archivos primero para la barra de progreso
    files = get_audio_files(processor.directory, recursive=processor.recursive)
    total_files = len(files)

    if total_files == 0:
        return {
            "total": 0,
            "recognized": 0,
            "lyrics_found": 0,
            "lyrics_embedded": 0,
            "results": {},
        }

    lyrics_results = {}

    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=None, complete_style="cyan", finished_style="green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=True,
    ) as progress:
        task_id = progress.add_task("Iniciando...", total=total_files)

        def progress_callback(file_path, result):
            filename = os.path.basename(file_path)
            # Truncar nombre si es muy largo para evitar saltos visuales
            if len(filename) > 40:
                filename = filename[:37] + "..."

            status = ""
            if result.get("error"):
                status = "[red]Error[/red]"
            elif result.get("metadata_error"):
                status = "[red]Error Meta[/red]"
            elif result.get("recognition"):
                status = "[green]Reconocido[/green]"
            elif result.get("lyrics_found"):
                status = "[green]Letra OK[/green]"
            elif result.get("metadata_updated"):
                status = "[green]Actualizado[/green]"
            else:
                status = "[dim]Sin cambios[/dim]"

            progress.update(
                task_id,
                advance=1,
                description=f"Procesando: [bold white]{filename}[/bold white] - {status}",
            )

        lyrics_results = processor.process_files(
            use_recognition=use_recognition,
            process_lyrics=process_lyrics,
            fetch_covers=fetch_covers,
            progress_callback=progress_callback,
        )

    stats = {
        "total": 0,
        "recognized": 0,
        "lyrics_found": 0,
        "lyrics_embedded": 0,
        "results": lyrics_results,
    }

    if not lyrics_results:
        return stats

    stats["total"] = len(lyrics_results)
    stats["recognized"] = sum(
        1 for _, r in lyrics_results.items() if r.get("recognition", False)
    )
    stats["lyrics_found"] = sum(
        1 for _, r in lyrics_results.items() if r.get("lyrics_found", False)
    )
    stats["lyrics_embedded"] = sum(
        1 for _, r in lyrics_results.items() if r.get("lyrics_embedded", False)
    )

    return stats


def add_covers(directory: Path) -> None:
    try:
        import core.install_covers as install_covers

        # Contar archivos primero (aproximado, install_covers lo hace de nuevo pero necesitamos el total para la barra)
        files = get_audio_files(directory)
        total_files = len(files)

        if total_files == 0:
            console.print("[yellow]No se encontraron archivos de audio.[/yellow]")
            return

        with Progress(
            SpinnerColumn(style="bold cyan"),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=None, complete_style="cyan", finished_style="green"),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
            expand=True,
        ) as progress:
            task_id = progress.add_task("Añadiendo portadas...", total=total_files)

            def progress_callback(file_path, result):
                filename = os.path.basename(file_path)
                if len(filename) > 40:
                    filename = filename[:37] + "..."

                status = ""
                if not result.get("status"):
                    status = "[red]Error[/red]"
                elif result.get("skipped"):
                    status = "[dim]Ya existe[/dim]"
                else:
                    status = "[green]Añadida[/green]"

                progress.update(
                    task_id,
                    advance=1,
                    description=f"Procesando: [bold white]{filename}[/bold white] - {status}",
                )

            install_covers.run(str(directory), progress_callback=progress_callback)

    except ImportError as e:
        raise RuntimeError(
            "No se pudo importar el módulo de instalación de portadas."
        ) from e
    except Exception as e:
        raise RuntimeError(f"Error al ejecutar la instalación de portadas: {e}") from e
