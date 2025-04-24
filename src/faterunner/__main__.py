import argparse
from pathlib import Path
from typing import Sequence

from . import parsers

_parsers = {
    'pyproject': parsers.pyproject_parser,
}


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('--parser', choices=_parsers.keys())
    parser.add_argument('-f', '--file', type=Path)
    parser.add_argument('target')
    return parser


def cli(argv: Sequence[str] | None = None) -> None:
    parser = make_parser()
    args = parser.parse_args(argv)

    manager = _parsers[args.parser](args.file.read_text())
    manager.run(args.target)


if __name__ == '__main__':
    cli(None)
