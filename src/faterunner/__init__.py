import dataclasses
import subprocess
from typing import MutableMapping, Protocol, Sequence


@dataclasses.dataclass(kw_only=True)
class Opts:
    silent: bool | None = None
    ignore_err: bool | None = None

    def __or__(self, other: 'Opts | None') -> 'Opts':
        if other is None:
            return self.__class__(**self.__dict__)
        update = {k: v for k, v in other.__dict__.items() if v is not None}
        new_dict = self.__dict__ | update
        return self.__class__(**new_dict)


class Action(Protocol):
    opts: Opts

    def run(self, opts: Opts | None = None) -> None: ...


class SubproccessAction:
    def __init__(self, cmd: Sequence[str], opts: Opts | None = None) -> None:
        if not opts:
            opts = Opts()

        self.cmd = cmd
        self.opts = opts

    def run(self, opts: Opts | None = None) -> None:
        opts = self.opts | opts

        proc = subprocess.run(
            self.cmd, stdout=subprocess.DEVNULL if opts.silent else None
        )
        if not opts.ignore_err:
            proc.check_returncode()


class Task:
    def __init__(
        self, actions: Sequence[Action], opts: Opts | None = None
    ) -> None:
        if not opts:
            opts = Opts()

        self.actions = actions
        self.opts = opts

    def run(self, opts: Opts | None = None) -> None:
        opts = self.opts | opts

        for action in self.actions:
            _ = action.run(opts)


class TaskManager:
    def __init__(
        self,
        tasks: MutableMapping[str, Task] | None = None,
        opts: Opts | None = None,
    ) -> None:
        if not tasks:
            tasks = {}
        if not opts:
            opts = Opts()

        self.tasks = tasks
        self.opts = opts

    def add(self, name: str, task: Task) -> None:
        self.tasks[name] = task

    def run(self, name: str, opts: Opts | None = None) -> None:
        opts = self.opts | opts

        task = self.tasks[name]
        task.run(opts)
