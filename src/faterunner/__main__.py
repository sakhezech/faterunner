import argparse
import importlib.metadata
import logging
import sys
from pathlib import Path
from typing import NoReturn, Sequence

from . import Opts, parsers

_parsers: dict[str, parsers.Parser] = {
    **{
        entry_point.name: entry_point.load()()
        for entry_point in importlib.metadata.entry_points(
            group='faterunner.parsers'
        )
    },
    'pyproject': parsers.PyprojectParser(),
}


logger = logging.getLogger('faterunner.cli')


def setup_logging(level: str, verbosity: int = 0) -> None:
    # HACK: this setup is temporary

    if verbosity >= 1:
        format = '%(asctime)s %(name)s: [%(levelname)s] %(message)s'
    else:
        format = '%(name)s: [%(levelname)s] %(message)s'

    logging.basicConfig(format=format)
    logging.getLogger('faterunner').setLevel(level)


def guess_file_and_parser() -> tuple[Path, str]:
    for name, parser in _parsers.items():
        file = parser.find_config_file()
        if file:
            return file, name
    raise RuntimeError("couldn't guess file and parser")


def guess_file(parser: str) -> Path:
    file = _parsers[parser].find_config_file()
    if file:
        return file
    raise RuntimeError(f"couldn't guess the file for parser: {parser}")


def guess_parser(file: Path) -> str:
    for name, parser in _parsers.items():
        if parser.validate_file_name(file):
            return name
    raise RuntimeError(f"couldn't guess the parser for file: {file}")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='the fate of a task is to be run'
    )

    opts_group = parser.add_argument_group()
    opts_group.add_argument(
        '--silent',
        action=argparse.BooleanOptionalAction,
        help='suppress output',
    )
    opts_group.add_argument(
        '--ignore-err',
        action=argparse.BooleanOptionalAction,
        help='ignore any error',
    )
    opts_group.add_argument(
        '--keep-going',
        action=argparse.BooleanOptionalAction,
        help='keep running tasks even if some cannot be done',
    )
    opts_group.add_argument(
        '--dry',
        action=argparse.BooleanOptionalAction,
        help='do not execute actions',
    )

    parser.add_argument(
        '--parser',
        choices=_parsers.keys(),
        help='parser to use (defaults to a guess)',
    )
    parser.add_argument(
        '-f',
        '--file',
        type=Path,
        help='configuration file (defaults to a guess)',
    )
    parser.add_argument(
        '-l', '--list', action='store_true', help='print all tasks and exit'
    )
    parser.add_argument(
        '--logging',
        default='INFO',
        choices=logging.getLevelNamesMapping().keys(),
        help='logging level (defaults to INFO)',
    )
    parser.add_argument(
        '-V',
        action='count',
        dest='verbosity',
        default=0,
        help='logging verbosity (more Vs more info)',
    )
    parser.add_argument('target', nargs='?', help='task to execute')
    return parser


def cli(argv: Sequence[str] | None = None) -> None:
    parser = make_parser()
    args = parser.parse_args(argv)
    setup_logging(args.logging, args.verbosity)

    try:
        if args.file is None and args.parser is None:
            args.file, args.parser = guess_file_and_parser()
            logger.debug(f'Guessed parser: {args.parser}')
            logger.debug(f'Guessed file: {args.file}')
        elif args.file is None:
            args.file = guess_file(args.parser)
            logger.debug(f'Guessed file: {args.file}')
        elif args.parser is None:
            args.parser = guess_parser(args.file)
            logger.debug(f'Guessed parser: {args.parser}')
    except RuntimeError as err:
        print_and_exit(err.args[0])

    manager = _parsers[args.parser].parse(args.file.read_text())

    if args.list:
        print_and_exit('Targets:', *manager.tasks.keys(), exit_code=0)

    if args.target is None:
        args.target = tuple(manager.tasks.keys())[0]
        logger.debug(f'Guessed target: {args.target}')

    logger.debug(
        f'File: {args.file}, Parser: {args.parser}, Target: {args.target}',
    )

    opts = Opts(
        silent=args.silent,
        ignore_err=args.ignore_err,
        keep_going=args.keep_going,
        dry=args.dry,
    )
    logger.debug(f'Force options: {opts}')

    try:
        manager.run(args.target, opts)
    except Exception:
        sys.exit(1)


def print_and_exit(*values, exit_code: int = 1) -> NoReturn:
    file = sys.stdout if exit_code == 0 else sys.stderr
    print(*values, file=file)
    sys.exit(exit_code)


if __name__ == '__main__':
    cli(None)
