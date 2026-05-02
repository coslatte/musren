import sys
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")


def main(interactive: bool = True) -> None:
    if interactive and len(sys.argv) == 1:
        from core.cli.shell import cli as musren_shell
        musren_shell()
    else:
        from core.cli.shell import InteractiveShell
        shell = InteractiveShell()
        if len(sys.argv) > 1:
            cmd = " ".join(sys.argv[1:])
            shell.run_command(cmd)
        else:
            shell.run()


if __name__ == "__main__":
    main()