import argparse
import sys
from pathlib import Path
from typing import NoReturn, Sequence

from . import Opts, parsers
from .exceptions import GuessError

_parsers: dict[str, parsers.Parser] = {
    'pyproject': parsers.PyprojectParser(),
}


def guess_file_and_parser() -> tuple[Path, str]:
    for name, parser in _parsers.items():
        file = parser.find_config_file()
        if file:
            return file, name
    raise GuessError("couldn't guess file and parser")


def guess_file(parser: str) -> Path:
    file = _parsers[parser].find_config_file()
    if file:
        return file
    raise GuessError(f"couldn't guess the file for parser: {parser}")


def guess_parser(file: Path) -> str:
    for name, parser in _parsers.items():
        if parser.validate_file_name(file):
            return name
    raise GuessError(f"couldn't guess the parser for file: {file}")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()

    opts_group = parser.add_argument_group()
    opts_group.add_argument(
        '--silent',
        action=argparse.BooleanOptionalAction,
    )
    opts_group.add_argument(
        '--ignore-err',
        action=argparse.BooleanOptionalAction,
    )
    opts_group.add_argument(
        '--keep-going',
        action=argparse.BooleanOptionalAction,
    )
    opts_group.add_argument(
        '--dry',
        action=argparse.BooleanOptionalAction,
    )

    parser.add_argument('--parser', choices=_parsers.keys())
    parser.add_argument('-f', '--file', type=Path)
    parser.add_argument('-l', '--list', action='store_true')
    parser.add_argument('target', nargs='?')
    return parser


def cli(argv: Sequence[str] | None = None) -> None:
    parser = make_parser()
    args = parser.parse_args(argv)

    try:
        if args.file is None and args.parser is None:
            args.file, args.parser = guess_file_and_parser()
        elif args.file is None:
            args.file = guess_file(args.parser)
        elif args.parser is None:
            args.parser = guess_parser(args.file)
    except GuessError as err:
        print_and_exit(err.args[0])

    manager = _parsers[args.parser].parse(args.file.read_text())

    if args.list:
        print_and_exit('Targets:', *manager.tasks.keys(), exit_code=0)

    if args.target is None:
        args.target = tuple(manager.tasks.keys())[0]

    opts = Opts(
        silent=args.silent,
        ignore_err=args.ignore_err,
        keep_going=args.keep_going,
        dry=args.dry,
    )

    manager.run(args.target, opts)


def print_and_exit(*values, exit_code: int = 1) -> NoReturn:
    file = sys.stdout if exit_code == 0 else sys.stderr
    print(*values, file=file)
    sys.exit(exit_code)


if __name__ == '__main__':
    cli(None)
