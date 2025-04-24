import shlex
from typing import Mapping

from . import SubproccessAction, Task, TaskManager


def pyproject_parser(
    string: str, tool_name: str = 'faterunner'
) -> TaskManager:
    import tomllib

    manager = TaskManager()

    conf = tomllib.loads(string)

    assert 'tool' in conf
    assert tool_name in conf['tool']

    tool_config = conf['tool'][tool_name]
    assert isinstance(tool_config, Mapping)

    for name, action_strings in tool_config.items():
        actions = [
            SubproccessAction(shlex.split(action_string))
            for action_string in action_strings
        ]
        manager.add(name, Task(actions))

    return manager
