import abc
import contextlib
import dataclasses
import logging
import os
import subprocess
import sys
from typing import Callable, Generator, Iterable, MutableMapping, Sequence

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
    def get_name(self) -> str: ...

    def run(self, opts: Opts | None = None) -> None:
        opts = self.opts | opts

        logger.debug(f'Current action: {self}')
        logger.debug(f'Action options: {opts}')
        logger.info(self.get_name())
        if opts.dry:
            return

        if opts.silent:
            output_redirect = self.redirect_stdout_stderr()
        else:
            output_redirect = contextlib.nullcontext()
        try:
            # NOTE: if you want you can capture output in silent
            # instead of devnull'ing it and attach it to the err if raised
            with output_redirect:
                self._run(opts)

        except Exception as err:
            # because ignore_err is supposed to suppress any error in execution
            # we have to deal with it here
            # i.e. we can't let it go to Manager._run where all the logging is
            # so we have to log it here ourselves
            if not opts.ignore_err:
                raise err
            logger.info(f'{err} (ignored)')

    @contextlib.contextmanager
    def redirect_stdout_stderr(self) -> Generator[None]:
        with (
            open(os.devnull, 'w') as nullout,
            open(os.devnull, 'w') as nullerr,
        ):
            with contextlib.redirect_stdout(nullout):
                with contextlib.redirect_stderr(nullerr):
                    yield


class SubprocessAction(Action):
    def __init__(self, cmd: str, opts: Opts | None = None) -> None:
        if not opts:
            opts = Opts()

        self.cmd = cmd
        self.opts = opts

    def get_name(self) -> str:
        return self.cmd

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({repr(self.cmd)})'

    def _run(self, opts: Opts) -> None:
        _ = opts
        proc = subprocess.run(
            self.cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
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

    def get_name(self) -> str:
        return self.func.__name__

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({repr(self.func)})'

    def _run(self, opts: Opts) -> None:
        _ = opts
        self.func(*self.args, **self.kwargs)


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
            raise RuntimeError(*exceptions)

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
            if name not in self.tasks:
                raise KeyError(f'No such task: {name}')

            failed_deps = [dep for dep in deps if dep in failed]
            if failed_deps:
                raise RuntimeError(
                    f"Dependencies failed for '{name}': "
                    f'{" ".join(failed_deps)}'
                )

            # NOTE: i don't know if we can even hit this condition
            # but i think we should check regardless
            # we can't run a task if the deps are not satisfied
            not_run_deps = [dep for dep in deps if dep not in already_run]
            if not_run_deps:
                raise RuntimeError(
                    f"Dependencies not run for '{name}': "
                    f'{" ".join(not_run_deps)}'
                )
            self.tasks[name].run(opts)

        # NOTE: i think all the error logging should be done here
        # at least for all errors that are supposed to crash
        # i.e. not ignore_err errors
        except Exception as err:
            failed.add(name)
            exceptions.add(err)
            logger.error(err)
            if not opts.keep_going:
                raise err

        return exceptions
