import abc
import shlex
from pathlib import Path
from typing import Mapping

from . import Manager, SubproccessAction, Task


class Parser(abc.ABC):
    @abc.abstractmethod
    def parse(self, string: str) -> Manager: ...
    @abc.abstractmethod
    def validate_file_name(self, file: Path) -> bool: ...
    @abc.abstractmethod
    def validate_choice(self, file: Path) -> bool: ...

    def find_config_file(self) -> Path | None:
        for file in Path.cwd().iterdir():
            if self.validate_file_name(file) and self.validate_choice(file):
                return file
        return None


class PyprojectParser(Parser):
    def __init__(self, tool_name: str = 'faterunner') -> None:
        self.tool_name = tool_name

    def parse(self, string: str) -> Manager:
        import tomllib

        manager = Manager()

        conf = tomllib.loads(string)

        assert 'tool' in conf
        assert self.tool_name in conf['tool']

        tool_config = conf['tool'][self.tool_name]
        assert isinstance(tool_config, Mapping)

        for name, action_strings in tool_config.items():
            actions = [
                SubproccessAction(shlex.split(action_string))
                for action_string in action_strings
            ]
            manager.add(name, Task(actions))

        return manager

    def validate_file_name(self, file: Path) -> bool:
        return file.name == 'pyproject.toml'

    # validates if this is the file we want to choose
    # for example a pyproject.toml file can be our configuration file
    # if it has [tool.faterunner...] section, and if it doesn't we should
    # look elsewhere
    # TODO: maybe rename, i am not sure
    def validate_choice(self, file: Path) -> bool:
        # HACK: quick and dirty and wrong, fix
        return f'[tool.{self.tool_name}' in file.read_text()
