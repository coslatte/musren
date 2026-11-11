from rich import print
from rich.box import SIMPLE_HEAVY
from rich.panel import Panel
from rich.table import Table

from core.cli.config import VALID_KEYS, get_config_manager


def config_list_shell() -> None:
    """List config - optimized for shell."""
    config = get_config_manager()
    if config.load_error:
        print(f"[red]Configuration could not be read: {config.load_error}[/red]")
        return
    try:
        keys = config.list_keys()
    except OSError as error:
        print(f"[red]Credentials could not be accessed: {error}[/red]")
        return

    table = Table(title="API Keys", box=SIMPLE_HEAVY)
    table.add_column("Key", style="bold cyan")
    table.add_column("Status", style="white")
    table.add_column("Description", style="dim")

    for key, description in VALID_KEYS.items():
        value = keys.get(key, "<not set>")
        table.add_row(key, value, description)

    print(table)


def config_set_shell(key: str, value: str) -> None:
    """Set config - optimized for shell."""
    if key not in VALID_KEYS:
        print(f"[red]Invalid key: {key}[/red]")
        print(f"Valid keys: {', '.join(VALID_KEYS.keys())}")
        return

    config = get_config_manager()
    try:
        config.set(key, value)
    except OSError as error:
        print(f"[red]Credentials could not be saved: {error}[/red]")
        return

    # 2026-11-09: evita exponer el secreto recién guardado en la terminal.
    print(
        Panel(
            f"[green]Set {key} in the OS credential store[/green]",
            border_style="green",
            title="Config Updated",
        )
    )


def config_get_shell(key: str) -> None:
    """Get config - optimized for shell."""
    if key not in VALID_KEYS:
        print(f"[red]Invalid key: {key}[/red]")
        print(f"Valid keys: {', '.join(VALID_KEYS.keys())}")
        return

    config = get_config_manager()
    if config.load_error:
        print(f"[red]Configuration could not be read: {config.load_error}[/red]")
        return
    try:
        value = config.get(key)
    except OSError as error:
        print(f"[red]Credentials could not be accessed: {error}[/red]")
        return

    if value:
        print(f"[cyan]{key}[/cyan] = [white]{value}[/white]")
    else:
        print(f"[yellow]{key}[/yellow] is not set")


def config_delete_shell(key: str) -> None:
    """Delete config - optimized for shell."""
    if key not in VALID_KEYS:
        print(f"[red]Invalid key: {key}[/red]")
        print(f"Valid keys: {', '.join(VALID_KEYS.keys())}")
        return

    config = get_config_manager()
    try:
        deleted = config.delete(key)
    except OSError as error:
        print(f"[red]Credentials could not be deleted: {error}[/red]")
        return

    if deleted:
        print(
            Panel(
                f"[green]Deleted {key}[/green]",
                border_style="yellow",
                title="Config Updated",
            )
        )
    else:
        print(f"[yellow]{key}[/yellow] was not set")
