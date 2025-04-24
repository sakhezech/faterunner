import argparse
from typing import Sequence


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    return parser


def cli(argv: Sequence[str] | None = None) -> None:
    parser = make_parser()
    args = parser.parse_args(argv)
    _ = args


if __name__ == '__main__':
    cli(None)
