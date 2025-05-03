import abc
import contextlib
import dataclasses
import io
import logging
import subprocess
from typing import (
    Callable,
    Generator,
    Iterable,
    MutableMapping,
    Sequence,
)

from .exceptions import ActionError, DependencyError, FateError

logger = logging.getLogger('faterunner')


@dataclasses.dataclass(kw_only=True)
class Opts:
    silent: bool | None = None
    ignore_err: bool | None = None
    keep_going: bool | None = None
    dry: bool | None = None

    def __or__(self, other: 'Opts | None') -> 'Opts':
        if other is None:
            return self.__class__(**self.__dict__)
        update = {k: v for k, v in other.__dict__.items() if v is not None}
        new_dict = self.__dict__ | update
        return self.__class__(**new_dict)


class Action(abc.ABC):
    opts: Opts

    @abc.abstractmethod
    def _run(self, opts: Opts) -> None: ...

    @abc.abstractmethod
    def action_repr(self) -> str: ...

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.action_repr().__repr__()})'

    def run(self, opts: Opts | None = None) -> None:
        opts = self.opts | opts

        logger.debug(f'Current action: {self}')
        logger.debug(f'Action options: {opts}')
        logger.info(self.action_repr())
        if opts.dry:
            return

        try:
            self._run(opts)
        except Exception as err:
            # because ignore_err is supposed to suppress any error in execution
            # we have to deal with it here
            # i.e. we can't let it go to Manager._run where all the logging is
            # so we have to log it here ourselves
            if not opts.ignore_err:
                raise ActionError(err)
            logger.info(f'{err} (ignored)')


class SubprocessAction(Action):
    def __init__(self, cmd: str, opts: Opts | None = None) -> None:
        if not opts:
            opts = Opts()

        self.cmd = cmd
        self.opts = opts

    def action_repr(self) -> str:
        return self.cmd

    def _run(self, opts: Opts) -> None:
        proc = subprocess.run(
            self.cmd,
            stdout=subprocess.DEVNULL if opts.silent else None,
            stderr=subprocess.DEVNULL if opts.silent else None,
            shell=True,
        )
        proc.check_returncode()


class FunctionAction[**P, T](Action):
    def __init__(
        self,
        func: Callable[P, T],
        opts: Opts | None = None,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        if not opts:
            opts = Opts()

        self.func = func
        self.opts = opts
        self.args = args
        self.kwargs = kwargs

    def action_repr(self) -> str:
        return self.func.__name__

    def _run(self, opts: Opts) -> None:
        if opts.silent:
            context = self.redirect_stdout_stderr()
        else:
            context = contextlib.nullcontext()
        with context:
            self.func(*self.args, **self.kwargs)

    @contextlib.contextmanager
    def redirect_stdout_stderr(self) -> Generator[None]:
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                yield


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
        logger.debug(f'Task options: {opts}')

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
        logger.debug(f'Manager options: {opts}')

        exceptions = self._run(name, opts)
        if exceptions:
            # TODO: raise other type of err
            raise FateError(*exceptions)

    def _run(
        self,
        name: str,
        opts: Opts,
        already_run: set[str] | None = None,
        failed: set[str] | None = None,
        exceptions: set[Exception] | None = None,
    ) -> set[Exception]:
        already_run = already_run if already_run is not None else set()
        failed = failed if failed is not None else set()
        exceptions = exceptions if exceptions is not None else set()

        if name in already_run:
            logger.debug(f'Skipping deduped task: {name}')
            return exceptions
        already_run.add(name)
        logger.debug(f'Adding task to dedupe: {name}')

        deps = self.deps.get(name, [])
        if deps:
            logger.debug(f"Dependencies for '{name}': {' '.join(deps)}")
        for dep in deps:
            logger.debug(f"Running dependency for '{name}': {dep}")
            self._run(dep, opts, already_run, failed, exceptions)

        logger.debug(f'Current task: {name}')
        try:
            failed_deps = [dep for dep in deps if dep in failed]
            if failed_deps:
                raise DependencyError(
                    f"Dependencies failed for '{name}': "
                    f'{" ".join(failed_deps)}'
                )

            # NOTE: i don't know if we can even hit this condition
            # but i think we should check regardless
            # we can't run a task if the deps are not satisfied
            not_run_deps = [dep for dep in deps if dep not in already_run]
            if not_run_deps:
                raise DependencyError(
                    f"Dependencies not run for '{name}': "
                    f'{" ".join(not_run_deps)}'
                )
            self.tasks[name].run(opts)

        # NOTE: i think all the error logging should be done here
        # at least for all errors that are supposed to crash
        # i.e. not ignore_err errors
        except (DependencyError, ActionError) as err:
            failed.add(name)
            exceptions.add(err)
            logger.error(err)
            if not opts.keep_going:
                raise err

        return exceptions
