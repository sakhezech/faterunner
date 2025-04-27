import dataclasses
import subprocess
from typing import Iterable, MutableMapping, Protocol, Sequence

from .exceptions import ActionError, DependencyError, FateError


@dataclasses.dataclass(kw_only=True)
class Opts:
    silent: bool | None = None
    ignore_err: bool | None = None
    keep_going: bool | None = None

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

        try:
            proc = subprocess.run(
                self.cmd,
                stdout=subprocess.DEVNULL if opts.silent else None,
                stderr=subprocess.DEVNULL if opts.silent else None,
            )
            proc.check_returncode()
        except (OSError, subprocess.CalledProcessError) as err:
            # because ignore_err is supposed to suppress any error in execution
            # we have to deal with it here
            # i.e. we can't let it go to Manager._run where all the logging is
            # so we have to log it here ourselves
            if not opts.ignore_err:
                raise ActionError(err)
            # TODO: logging here


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


class Manager:
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
        self.deps: dict[str, Iterable[str]] = {}
        self.opts = opts

    def add(
        self, name: str, task: Task, deps: Iterable[str] | None = None
    ) -> None:
        if deps is None:
            deps = []

        self.tasks[name] = task
        self.deps[name] = deps

    def run(self, name: str, opts: Opts | None = None) -> None:
        opts = self.opts | opts

        exceptions = self._run(name, opts, set(), set(), set())
        if exceptions:
            # TODO: raise other type of err
            raise FateError(*exceptions)

    def _run(
        self,
        name: str,
        opts: Opts,
        already_run: set[str],
        failed: set[str],
        exceptions: set[Exception],
    ) -> set[Exception]:
        if name in already_run:
            return exceptions
        already_run.add(name)

        deps = self.deps.get(name, [])
        for dep in deps:
            self._run(dep, opts, already_run, failed, exceptions)

        try:
            failed_deps = [dep for dep in deps if dep in failed]
            if failed_deps:
                raise DependencyError(
                    f'dependencies failed: {" ".join(failed_deps)}'
                )

            # NOTE: i don't know if we can even hit this condition
            # but i think we should check regardless
            # we can't run a task if the deps are not satisfied
            not_run_deps = [dep for dep in deps if dep not in already_run]
            if not_run_deps:
                raise DependencyError(
                    f'dependencies not run: {" ".join(not_run_deps)}'
                )
            self.tasks[name].run(opts)

        # NOTE: i think all the error logging should be done here
        # at least for all errors that are supposed to crash
        # i.e. not ignore_err errors
        except (DependencyError, ActionError) as err:
            failed.add(name)
            exceptions.add(err)
            # TODO: logging here
            if not opts.keep_going:
                raise err

        return exceptions
