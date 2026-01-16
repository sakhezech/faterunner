import abc
import tomllib
from pathlib import Path

from pydantic import BaseModel

from . import Manager, Opts, SubprocessAction, Task


class Parser(abc.ABC):
    @abc.abstractmethod
    def parse(self, string: str) -> Manager: ...
    @abc.abstractmethod
    def validate_file(self, file: Path) -> bool: ...

    def find_config_file(self, root_path: Path) -> Path | None:
        for file in root_path.iterdir():
            if self.validate_file(file):
                return file
        return None


class PyprojectParser(Parser):
    class Target(BaseModel):
        commands: list[str] | None = None
        options: Opts | None = None
        dependencies: list[str] | None = None

    class Config(BaseModel):
        options: Opts | None = None
        targets: dict[str, 'list[str] | PyprojectParser.Target']

    def __init__(self, tool_name: str = 'faterunner') -> None:
        self.tool_name = tool_name

    def parse(self, string: str) -> Manager:
        pyproject = tomllib.loads(string)

        if 'tool' not in pyproject or self.tool_name not in pyproject['tool']:
            raise ValueError

        config = self.Config.model_validate(pyproject['tool'][self.tool_name])
        manager = Manager(opts=config.options)
        for name, task_content in config.targets.items():
            if isinstance(task_content, list):
                actions = [SubprocessAction(cmd) for cmd in task_content]
                manager.add(name, Task(actions))
            elif isinstance(task_content, self.Target):
                commands = task_content.commands or []
                opts = task_content.options
                deps = task_content.dependencies or []

                actions = [SubprocessAction(cmd) for cmd in commands]
                manager.add(name, Task(actions, opts), deps)
            else:
                raise TypeError(f'Target not list or mapping: {name}')

        return manager

    # validates if this is the file we want to choose
    # for example a pyproject.toml file can be our configuration file
    # if it has [tool.faterunner...] section, and if it doesn't we should
    # look elsewhere
    def validate_file(self, file: Path) -> bool:
        if file.name != 'pyproject.toml':
            return False
        string = file.read_text()
        conf = tomllib.loads(string)
        return 'tool' in conf and self.tool_name in conf['tool']
