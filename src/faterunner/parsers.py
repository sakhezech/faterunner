import abc
from pathlib import Path
from typing import Mapping

import tomllib

from . import Manager, Opts, SubprocessAction, Task


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

    # TODO: change assert to normal check and exceptions
    def parse(self, string: str) -> Manager:
        conf = tomllib.loads(string)

        assert 'tool' in conf
        assert self.tool_name in conf['tool']

        tool_config = conf['tool'][self.tool_name]
        assert isinstance(tool_config, Mapping)

        if 'options' in tool_config:
            assert isinstance(tool_config['options'], Mapping)
            opts = Opts(**tool_config['options'])
        else:
            opts = None
        manager = Manager(opts=opts)

        assert isinstance(tool_config['targets'], Mapping)
        for name, task_content in tool_config['targets'].items():
            if isinstance(task_content, list):
                actions = [SubprocessAction(cmd) for cmd in task_content]
                manager.add(name, Task(actions))
            elif isinstance(task_content, Mapping):
                commands = task_content.get('commands', [])
                opts = Opts(**task_content.get('options', {}))
                deps = task_content.get('dependencies', [])

                actions = [SubprocessAction(cmd) for cmd in commands]
                manager.add(name, Task(actions, opts))
                manager.deps[name] = deps
            else:
                raise TypeError(f'Target not list or mapping: {name}')

        return manager

    def validate_file_name(self, file: Path) -> bool:
        return file.name == 'pyproject.toml'

    # validates if this is the file we want to choose
    # for example a pyproject.toml file can be our configuration file
    # if it has [tool.faterunner...] section, and if it doesn't we should
    # look elsewhere
    def validate_choice(self, file: Path) -> bool:
        string = file.read_text()
        conf = tomllib.loads(string)
        return 'tool' in conf and self.tool_name in conf['tool']
