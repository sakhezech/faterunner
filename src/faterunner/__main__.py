import argparse
import sys
from pathlib import Path
from typing import NoReturn, Sequence

from . import parsers

_parsers = {
    'pyproject': parsers.pyproject_parser,
}


def guess_file() -> Path:
    return Path('./pyproject.toml')


def guess_parser(file: Path) -> str:
    if file.name == 'pyproject.toml':
        return 'pyproject'
    raise Exception(f"couldn't guess parser for file: {file}")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('--parser', choices=_parsers.keys())
    parser.add_argument('-f', '--file', type=Path)
    parser.add_argument('-l', '--list', action='store_true')
    parser.add_argument('target', nargs='?')
    return parser


def cli(argv: Sequence[str] | None = None) -> None:
    parser = make_parser()
    args = parser.parse_args(argv)

    if args.file is None:
        args.file = guess_file()
    if args.parser is None:
        args.parser = guess_parser(args.file)

    manager = _parsers[args.parser](args.file.read_text())

    if args.list:
        print_and_exit('Targets:', *manager.tasks.keys(), exit_code=0)

    if args.target is None:
        args.target = tuple(manager.tasks.keys())[0]

    manager.run(args.target)


def print_and_exit(*values, exit_code: int = 1) -> NoReturn:
    file = sys.stdout if exit_code == 0 else sys.stderr
    print(*values, file=file)
    sys.exit(exit_code)


if __name__ == '__main__':
    cli(None)
