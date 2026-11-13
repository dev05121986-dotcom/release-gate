import argparse
from pathlib import Path

from .checks import check
from .output import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release-gate")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("check", help="Valida o checklist do projeto atual")
    command.add_argument("--json", action="store_true", help="Emite um único objeto JSON")
    args = parser.parse_args(argv)
    result = check(Path.cwd())
    render(result, args.json)
    return result.exit_code
