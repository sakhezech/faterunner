# Faterunner

[![CI](https://github.com/sakhezech/faterunner/actions/workflows/ci.yaml/badge.svg)](https://github.com/sakhezech/faterunner/actions/workflows/ci.yaml)

The fate of a task if to be run.

Or "F.. A.. Task Execution Runner". (TODO: backronym)

## Parsers

Faterunner can support many configuration file formats.
It will try to guess the correct configuration file.

Right now Faterunner only supports `pyproject.toml` format, but you can
add your own file format support by implementing a parser and exposing it to
`faterunner.parsers` entry point

```toml
[project.entry-points.'faterunner.parsers']
my-parser = 'myproject.parser:MyParser'
```

### Pyproject

```toml
[tool.faterunner.targets]
# you can define a task as a list of commands
check = ['ruff check .', 'ruff format --check .']
format = ['ruff check --fix .', 'ruff format .']

# or you can define them as a table of {commands = ..., dependencies = ..., options = ...}
[tool.faterunner.targets.docker-build]
commands = ['docker build -t my-project:$(git rev-parse HEAD) .'] # interpolation
[tool.faterunner.targets.docker-run]
dependencies = ['build'] # will run only if `build` succeeded
commands = ['docker run --rm -p 5000:5000 my-project:$(git rev-parse HEAD)']

[tool.faterunner.targets.check-and-format]
dependencies = ['check', 'format'] # task with no commands

[tool.faterunner.targets.i-have-no-mouth-and-i-must-scream]
commands = ['echo "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAH"']
options = { silent = true } # inline options for the task
```

## Options

- `silent`: Suppress output. (stdout and stderr)
- `ignore_err`: Ignore any error.
- `keep_going`: Keep running tasks even if some cannot be done. (like `make -k ...`)
- `dry`: Do not execute actions.
