import os
from pathlib import Path
from typing import Optional

import traceback
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.traceback import Traceback

from constants.info import MUSIC_RENAMER_VERSION

console = Console()


class MenuItem:
    def __init__(self, id: int, name: str, description: str, command: str):
        self.id = id
        self.name = name
        self.description = description
        self.command = command


class Screen:
    def __init__(self, title: str, items: list[MenuItem]):
        self.title = title
        self.items = items
    
    def render(self) -> None:
        console.print(Panel(f"[bold cyan]{self.title}[/bold cyan]", border_style="cyan", expand=False))
        
        for item in self.items:
            console.print(f"  [yellow]{item.id}.[/yellow] [cyan]{item.name:<12}[/cyan] {item.description}")
        
        console.print()
        console.print("[dim]Press number or type command. Esc to go back.[/dim]")


class InteractiveShell:
    def __init__(self):
        self.running = True
        self.history = []
        self.current_dir = Path.cwd()
        self.screen_stack = []
        
        self.screens = self._create_screens()
        
        try:
            import readchar
            self._has_readchar = True
            self._readchar = readchar
        except ImportError:
            self._has_readchar = False

    def _get_input(self, prompt: str) -> str:
        if self._has_readchar:
            return self._get_input_with_readchar(prompt)
        return input(prompt)

    def _get_input_with_readchar(self, prompt: str) -> str:
        import sys
        result = []
        sys.stdout.write(prompt)
        sys.stdout.flush()
        
        while True:
            try:
                key = self._readchar.readkey()
            except EOFError:
                return ""
            except KeyboardInterrupt:
                return ""
            
            if key == "\n" or key == "\r":
                sys.stdout.write("\n")
                break
            elif key == "\x7f":
                if result:
                    result.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif key == "\x1b":
                return "ESC"
            else:
                result.append(key)
                sys.stdout.write(key)
                sys.stdout.flush()
        
        return "".join(result)

    def _create_screens(self) -> dict:
        return {
            "main": Screen("MusRen - Main Menu", [
                MenuItem(1, "Rename", "Rename audio files based on metadata", "rename"),
                MenuItem(2, "Lyrics", "Search and embed synchronized lyrics", "lyrics"),
                MenuItem(3, "Covers", "Add album covers to audio files", "covers"),
                MenuItem(4, "Recognize", "Recognize audio using AcoustID/Shazam", "recognize"),
                MenuItem(5, "Albums", "Organize files into album folders", "albums"),
                MenuItem(6, "Config", "Manage API keys and settings", "config"),
                MenuItem(7, "Help", "Show help and usage guide", "help"),
            ]),
            "config": Screen("Configuration", [
                MenuItem(1, "List", "Show all API keys", "config list"),
                MenuItem(2, "Set", "Set an API key", "config set"),
                MenuItem(3, "Get", "Get an API key", "config get"),
                MenuItem(4, "Delete", "Delete an API key", "config delete"),
                MenuItem(5, "Back", "Go back to main menu", "back"),
            ]),
        }

    def print_banner(self) -> None:
        console.print(f"[bold cyan]MusRen[/bold cyan] v{MUSIC_RENAMER_VERSION}")

    def show_main_menu(self) -> None:
        screen = self.screens["main"]
        console.print()
        
        panel_items = []
        for item in screen.items:
            panel_items.append(f"  [yellow]{item.id}.[/yellow] [cyan]{item.name:<12}[/cyan] {item.description}")
        help_text = "[dim]Commands: number, command, /exit, /help, /clear, /cd, /pwd[/dim]"
        if self._has_readchar:
            help_text += " [dim]| ESC, b = back to menu[/dim]"
        else:
            help_text += " [dim]| b = back to menu[/dim]"
        panel_items.extend(["", help_text])
        
        console.print(Panel(
            "\n".join(panel_items),
            title=f"[bold cyan]{screen.title}[/bold cyan]",
            border_style="cyan",
            expand=True,
            padding=(0, 2),
        ))
        console.print()
    
    def show_help(self) -> None:
        help_text = """[bold cyan]Available Commands[/bold cyan]

[yellow]Main Operations:[/yellow]
  [cyan]1. Rename[/cyan]      - Rename audio files based on metadata
  [cyan]2. Lyrics[/cyan]      - Search and embed synchronized lyrics
  [cyan]3. Covers[/cyan]      - Add album covers to audio files
  [cyan]4. Recognize[/cyan]    - Recognize audio using AcoustID/Shazam
  [cyan]5. Albums[/cyan]      - Organize files into album folders
  [cyan]6. Config[/cyan]      - Manage API keys and settings
  [cyan]7. Help[/cyan]        - Show this help guide

[yellow]Global Commands:[/yellow]
  [cyan]/help, ?[/cyan]       - Show this help
  [cyan]/exit, q[/cyan]       - Exit the application
  [cyan]/clear[/cyan]        - Clear the screen
  [cyan]/cd <path>[/cyan]    - Change directory
  [cyan]/pwd[/cyan]          - Show current directory
  [cyan]/version, -v[/cyan]   - Show version
  [cyan]b, back[/cyan]       - Return to main menu

[yellow]Usage Examples:[/yellow]
  [dim]# Rename files in current directory[/dim]
  [dim]  1[/dim]
  [dim]  rename[/dim]
  [dim]# Rename files in specific directory[/dim]
  [dim]  1 /path/to/music[/dim]
  [dim]  rename C:\\Music[/dim]
  [dim]# Set AcoustID API key[/dim]
  [dim]  6[/dim]
  [dim]  config set acoustid YOUR_KEY[/dim]
  [dim]# List all settings[/dim]
  [dim]  config list[/dim]

[yellow]Path Shortcuts:[/yellow]
  [dim]Enter or .[/dim]   - Use current directory
  [dim]/path/to/dir[/dim] - Use specified directory"""
        
        console.print(Panel(
            help_text,
            title="[bold cyan]MusRen Help[/bold cyan]",
            border_style="cyan",
            expand=True,
            padding=(0, 2),
        ))
        console.print()
    
    def show_config_menu(self) -> None:
        screen = self.screens["config"]
        
        panel_items = []
        for item in screen.items:
            panel_items.append(f"  [yellow]{item.id}.[/yellow] [cyan]{item.name:<12}[/cyan] {item.description}")
        
        console.print(Panel(
            "\n".join(panel_items),
            title=f"[bold cyan]{screen.title}[/bold cyan]",
            border_style="cyan",
            expand=False,
        ))
        console.print()

    def handle_number_input(self, input_str: str) -> str:
        screen = self.screens.get("main", self.screens["main"])
        try:
            num = int(input_str.strip())
            for item in screen.items:
                if item.id == num:
                    return item.command
        except ValueError:
            pass
        return input_str

    def run_command(self, input_line: str) -> bool:
        if not input_line.strip():
            return False
        
        parts = input_line.strip().split()
        cmd_name = parts[0].lower()
        args = parts[1:]
        
        console.rule(f"[bold cyan]{cmd_name}[/bold cyan]", style="cyan")
        
        try:
            if cmd_name in ("rename", "rn"):
                self._run_rename(args)
            elif cmd_name in ("lyrics", "lyr"):
                self._run_lyrics(args)
            elif cmd_name in ("covers", "cov"):
                self._run_covers(args)
            elif cmd_name in ("recognize", "rec"):
                self._run_recognize(args)
            elif cmd_name in ("albums", "alb"):
                self._run_albums(args)
            elif cmd_name in ("config", "cfg"):
                self._run_config(args)
            elif cmd_name in ("help", "?"):
                self.show_help()
            else:
                console.print(f"[red]Unknown command: {cmd_name}[/red]")
            return True
        except Exception as e:
            self._handle_error(e, cmd_name)
            return False

    def _handle_error(self, error: Exception, command: str = "") -> None:
        error_msg = str(error)
        error_type = type(error).__name__
        
        error_messages = {
            "No audio files found": "[yellow]No audio files found in the specified directory.[/yellow]\n[dim]Try a different directory or add audio files first.[/dim]",
            "Missing dependencies": "[red]Missing required dependencies.[/red]\n[dim]Install required packages: pip install mutagen requests[/dim]",
            "API key": "[yellow]API key not configured.[/yellow]\n[dim]Run: config set acoustid YOUR_KEY[/dim]",
            "Permission denied": "[red]Permission denied.[/red]\n[dim]Check file permissions or try a different directory.[/dim]",
            "Not found": "[red]Directory or file not found.[/red]\n[dim]Check the path and try again.[/dim]",
            "FileNotFoundError": "[red]File not found.[/red]\n[dim]Check if the file or directory exists.[/dim]",
            "IsADirectoryError": "[red]Expected a file, got a directory.[/red]\n[dim]Provide a file path, not a directory.[/dim]",
            "AttributeError": "[red]Internal error in command execution.[/red]\n[dim]Try specifying arguments explicitly. Use: command --help[/dim]",
            "TypeError": "[red]Invalid argument type.[/red]\n[dim]Check the command syntax. Use: command --help[/dim]",
            "ValueError": "[red]Invalid value provided.[/red]\n[dim]Check the arguments and try again.[/dim]",
        }
        
        matched = False
        for key, msg in error_messages.items():
            if key.lower() in error_msg.lower() or key == error_type:
                console.print(Panel(msg, title="[bold red]Error[/bold red]", border_style="red"))
                matched = True
                break
        
        if not matched:
            console.print(Panel(
                f"[red]Error in {command}[/red]\n[yellow]{error_msg}[/yellow]",
                title="[bold red]Error[/bold red]",
                border_style="red",
            ))
        
        console.print(f"[dim]Hint: Use /help for menu or b to go back.[/dim]")

    def _normalize_path_args(self, args: list) -> list:
        normalized = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg and not arg.startswith("-") and Path(arg).exists():
                normalized.extend(["--directory", arg])
            else:
                normalized.append(arg)
            i += 1
        return normalized

    def _prompt_for_path(self, command_name: str) -> Optional[str]:
        console.print(f"[cyan]Specify path for {command_name}:[/cyan]")
        console.print("[dim](Enter = current directory, . = current directory, or absolute path)[/dim]")
        prompt = f"[bold cyan]{command_name}[/bold cyan]$ "
        console.print(prompt, end="")
        path_input = input().strip()
        
        if not path_input or path_input == ".":
            return str(self.current_dir)
        
        return path_input

    def _run_rename(self, args: list) -> None:
        from click.testing import CliRunner
        from core.cli.commands.rename import rename_app
        
        if not args:
            path = self._prompt_for_path("rename")
            if not path:
                return
            args = [path]
        
        runner = CliRunner()
        normalized_args = self._normalize_path_args(args)
        result = runner.invoke(rename_app, ["run"] + normalized_args, catch_exceptions=False)
        if result.exit_code != 0:
            console.print(f"[red]Command exited with code {result.exit_code}[/red]")
            if result.output:
                console.print(result.output)

    def _run_lyrics(self, args: list) -> None:
        from click.testing import CliRunner
        from core.cli.commands.lyrics import lyrics_app
        
        if not args:
            path = self._prompt_for_path("lyrics")
            if not path:
                return
            args = [path]
        
        runner = CliRunner()
        normalized_args = self._normalize_path_args(args)
        result = runner.invoke(lyrics_app, ["run"] + normalized_args, catch_exceptions=False)
        if result.exit_code != 0:
            console.print(f"[red]Command exited with code {result.exit_code}[/red]")
            if result.output:
                console.print(result.output)

    def _run_covers(self, args: list) -> None:
        from click.testing import CliRunner
        from core.cli.commands.covers import covers_app
        
        if not args:
            path = self._prompt_for_path("covers")
            if not path:
                return
            args = [path]
        
        runner = CliRunner()
        normalized_args = self._normalize_path_args(args)
        result = runner.invoke(covers_app, ["run"] + normalized_args, catch_exceptions=False)
        if result.exit_code != 0:
            console.print(f"[red]Command exited with code {result.exit_code}[/red]")
            if result.output:
                console.print(result.output)

    def _run_recognize(self, args: list) -> None:
        from click.testing import CliRunner
        from core.cli.commands.recognize import recognize_app
        
        if not args:
            path = self._prompt_for_path("recognize")
            if not path:
                return
            args = [path]
        
        runner = CliRunner()
        normalized_args = self._normalize_path_args(args)
        result = runner.invoke(recognize_app, ["run"] + normalized_args, catch_exceptions=False)
        if result.exit_code != 0:
            console.print(f"[red]Command exited with code {result.exit_code}[/red]")
            if result.output:
                console.print(result.output)

    def _run_albums(self, args: list) -> None:
        from click.testing import CliRunner
        from core.cli.commands.albums import albums_app
        
        if not args:
            path = self._prompt_for_path("albums")
            if not path:
                return
            args = [path]
        
        runner = CliRunner()
        normalized_args = self._normalize_path_args(args)
        result = runner.invoke(albums_app, ["run"] + normalized_args, catch_exceptions=False)
        if result.exit_code != 0:
            console.print(f"[red]Command exited with code {result.exit_code}[/red]")
            if result.output:
                console.print(result.output)

    def _run_config(self, args: list) -> None:
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt
        
        console = Console()
        
        if not args:
            console.print(Panel(
                "[bold cyan]Config Options[/bold cyan]\n"
                "[yellow]1.[/yellow] list  - Show all API keys\n"
                "[yellow]2.[/yellow] set    - Set an API key\n"
                "[yellow]3.[/yellow] get    - Get an API key\n"
                "[yellow]4.[/yellow] delete - Delete an API key\n"
                "[yellow]b.[/yellow] back  - Return to main menu\n"
                "[dim]Or type: config <subcommand> <args>[/dim]",
                title="[bold cyan]Configuration[/bold cyan]",
                border_style="cyan",
                expand=True,
                padding=(0, 2),
            ))
            
            prompt = Prompt.ask(
                "[cyan]Select config option[/cyan]",
                choices=["1", "2", "3", "4", "b", "back"],
                default="1"
            )
            
            if prompt in ("b", "back"):
                return
            
            if prompt == "1":
                args = ["list"]
            elif prompt == "2":
                key = Prompt.ask("[cyan]Enter key name[/cyan]", choices=list({"acoustid"}))
                value = Prompt.ask("[cyan]Enter value[/cyan]")
                args = ["set", key, value]
            elif prompt == "3":
                key = Prompt.ask("[cyan]Enter key name[/cyan]", choices=list({"acoustid"}))
                args = ["get", key]
            elif prompt == "4":
                key = Prompt.ask("[cyan]Enter key name[/cyan]", choices=list({"acoustid"}))
                args = ["delete", key]
        
        try:
            from core.cli.commands.config_shell import config_list_shell, config_set_shell, config_get_shell, config_delete_shell
            
            if not args or args[0] == "list":
                config_list_shell()
            elif args[0] == "set" and len(args) >= 3:
                config_set_shell(args[1], " ".join(args[2:]))
            elif args[0] == "get" and len(args) >= 2:
                config_get_shell(args[1])
            elif args[0] == "delete" and len(args) >= 2:
                config_delete_shell(args[1])
            else:
                console.print("[yellow]Usage: config list | set <key> <value> | get <key> | delete <key>[/yellow]")
        except Exception as e:
            console.print(Panel(
                f"[red]Error in config command[/red]\n[yellow]{str(e)}[/yellow]",
                title="[bold red]Error[/bold red]",
                border_style="red",
            ))

    def run(self) -> None:
        self.print_banner()
        
        welcome = """[bold cyan]MusRen[/bold cyan] - Music file organizer

[dim]Version {version}[/dim]""".format(version=MUSIC_RENAMER_VERSION)
        console.print(Panel(welcome, border_style="cyan", expand=True, padding=(0, 2)))
        
        self.show_main_menu()

        while self.running:
            try:
                prompt = f"[bold cyan]MusRen[/bold cyan] [yellow]{self.current_dir.name}[/yellow]$ "
                if self._has_readchar:
                    console.print(prompt, end="")
                    choice = self._get_input("").strip()
                else:
                    console.print(prompt, end="")
                    choice = input().strip()
                
                if choice == "ESC":
                    console.print("[cyan]Returning to main menu...[/cyan]")
                    self.show_main_menu()
                    continue

                if not choice:
                    continue

                self.history.append(choice)

                if choice.lower() in ("/exit", "/quit", "exit", "quit", "q", "x"):
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                elif choice.lower() in ("b", "back", "backmenu"):
                    console.print("[cyan]Returning to main menu...[/cyan]")
                    self.show_main_menu()
                    continue
                elif choice.lower() in ("--version", "-v"):
                    console.print(f"[bold cyan]MusRen[/bold cyan] v{MUSIC_RENAMER_VERSION}")
                elif choice.lower() in ("/help", "?", "help"):
                    self.show_help()
                elif choice.lower() == "/clear":
                    console.clear()
                    self.print_banner()
                elif choice.lower().startswith("/cd "):
                    new_dir = choice[4:].strip()
                    new_path = Path(new_dir).expanduser()
                    if new_path.is_dir():
                        self.current_dir = new_path.resolve()
                        os.chdir(self.current_dir)
                    else:
                        console.print(f"[red]Directory not found: {new_dir}[/red]")
                elif choice.lower() in ("/pwd", "pwd"):
                    console.print(f"[cyan]{self.current_dir}[/cyan]")
                elif choice.isdigit():
                    result = self.handle_number_input(choice)
                    if result == "/help":
                        self.show_main_menu()
                    elif result == "back":
                        self.show_main_menu()
                    else:
                        self.run_command(result)
                        self.show_main_menu()
                elif choice.startswith("/"):
                    console.print(f"[red]Unknown: {choice}[/red]")
                else:
                    self.run_command(choice)
                    self.show_main_menu()

                console.print()

            except KeyboardInterrupt:
                console.print("\n[dim]Use /exit to quit[/dim]")
            except EOFError:
                break
            except Exception as e:
                console.print(Panel(str(e), title="[bold red]Error[/bold red]", border_style="red"))
                console.print()
                self.show_main_menu()


def cli() -> None:
    shell = InteractiveShell()
    shell.run()


if __name__ == "__main__":
    cli()