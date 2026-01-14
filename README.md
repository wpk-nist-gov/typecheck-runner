<!-- markdownlint-disable MD041 -->

<!-- prettier-ignore-start -->
[![Repo][repo-badge]][repo-link]
[![PyPI license][license-badge]][license-link]
[![PyPI version][pypi-badge]][pypi-link]
[![Code style: ruff][ruff-badge]][ruff-link]
[![uv][uv-badge]][uv-link]

<!--
  For more badges, see
  https://shields.io/category/other
  https://naereen.github.io/badges/
  [pypi-badge]: https://badge.fury.io/py/typecheck-runner
-->

[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff-link]: https://github.com/astral-sh/ruff
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv-link]: https://github.com/astral-sh/uv
[pypi-badge]: https://img.shields.io/pypi/v/typecheck-runner
[pypi-link]: https://pypi.org/project/typecheck-runner
[repo-badge]: https://img.shields.io/badge/--181717?logo=github&logoColor=ffffff
[repo-link]: https://github.com/wpk-nist-gov/typecheck-runner
[license-badge]: https://img.shields.io/pypi/l/typecheck-runner?color=informational
[license-link]: https://github.com/wpk-nist-gov/typecheck-runner/blob/main/LICENSE
[changelog-link]: https://github.com/wpk-nist-gov/typecheck-runner/blob/main/CHANGELOG.md

<!-- other links -->

[mypy]: https://github.com/python/mypy
[pyright]: https://github.com/microsoft/pyright
[basedpyright]: https://github.com/DetachHead/basedpyright
[ty]: https://github.com/astral-sh/ty
[pyrefly]: https://github.com/microsoft/pyright
<!-- [pre-commit]: https://pre-commit.com/ -->
<!-- [prek]: https://github.com/j178/prek -->

<!-- prettier-ignore-end -->

# `typecheck-runner`

A unified way to run globally installed typecheckers against a specified virtual
environment.

## Overview

I prefer to invoke globally managed type checkers against specified virtual
environments. For cases where python versions are checked against (with, for
example tox or nox), this prevents each virtual environment from having to
contain a type checker. Each type checker ([mypy], [pyright], [basedpyright],
[ty], and [pyrefly]) has it's own particular flags to specify the python
executable and the python version. `typecheck-runner` unifies these flags. Also,
by default, `typecheck-runner` invokes the type checker using
[`uvx`](https://docs.astral.sh/uv/guides/tools/), which installs the type
checker if needed.

## Usage

### Install into virtual environment

The easiest way to use `typecheck-runner` is to install it into the virtual
environment you'd like to test against using something like

```bash
pip install typecheck-runner
```

from the virtual environment of interest. To invoke a type checker against the
virtual environment, assuming the python executable of the virtual environment
is located at `/path/to/venv/bin` with python version `3.13`, use

```bash
typecheck-runner --check mypy
# runs: uvx mypy --python-version=3.13 --python-executable=/path/to/venv/bin
```

Where the commented line shows the command run. Specifying `--no-uvx` will
instead invoke the type checker without `uvx`, so the type checker must already
be installed.

You can specify multiple checkers with multiple `--check` flags. To specify
options to `uvx` for each checker, pass options after `--uvx-delimiter` which
defaults to `--`. For example:

```bash
typecheck-runner --check "mypy --verbose -- --reinstall"
# runs: uvx --reinstall mypy --verbose
```

You can specify `uvx` options to all checkers using the `--uvx-options` flag.

### Specify virtual environment

You can also use a globally installed `typecheck-runner` and specify which
virtual environment to test over using `--venv` or `--infer-venv` options. For
example, you can use:

```bash
uvx typecheck-runner --venv .venv --check mypy
# run for example (if .venv current directory with version 3.14)
#   uvx mypy --python-version=3.14 --python-executable=.venv/bin/python
```

Using `--infer-venv` will attempt to infer the virtual environment from, in
order, environment variables `VIRTUAL_ENV`, `CONDA_PREFIX`, and finally `.venv`
in current directory.

## Options

<!-- markdownlint-disable-next-line MD013 -->
<!-- [[[cog
import sys
sys.path.insert(0, ".")
from tools.cog_utils import wrap_command, get_pyproject, run_command, cat_lines
sys.path.pop(0)
]]] -->
<!-- [[[end]]] -->

<!-- prettier-ignore-start -->
<!-- markdownlint-disable MD013 -->
<!-- [[[cog run_command("typecheck-runner --help", include_cmd=False, wrapper="restructuredtext")]]] -->

```restructuredtext
usage: typecheck-runner [-h] [--version] [-c CHECKERS]
                        [--python-executable PYTHON_EXECUTABLE]
                        [--python-version PYTHON_VERSION] [--no-python-executable]
                        [--no-python-version] [--venv VENV] [--infer-venv]
                        [--constraints CONSTRAINTS] [-v] [--stdout] [--allow-errors]
                        [--fail-fast] [--dry-run] [--no-uvx] [--uvx-options UVX_OPTIONS]
                        [--uvx-delimiter UVX_DELIMITER]
                        [args ...]

Run executable using uvx.

positional arguments:
  args                  Extra files/arguments passed to all checkers.

options:
  -h, --help            show this help message and exit
  --version             Display version.
  -c, --check CHECKERS  Checker to run. This can be a string with options to the
                        checker. For example, ``--check "mypy --verbose"`` runs the
                        checker the command ``mypy --verbose``. Options after
                        ``uvx_delimiter`` (default ``"--"``, see ``--uvx-delimiter``
                        options) are treated as ``uvx`` options. For example, passing
                        ``--check "mypy --verbose -- --reinstall"`` will run ``uvx
                        --reinstall mypy --verbose``. Can be specified multiple times.
  --python-executable PYTHON_EXECUTABLE
                        Path to python executable. Defaults to ``sys.executable``. This
                        is passed to ``--python-executable`` (mypy), ``--pythonpath`` in
                        ((based)pyright), ``--python`` (ty), ``--python-interpreter-
                        path`` (pyrefly), and ignored for pylint.
  --python-version PYTHON_VERSION
                        Python version (x.y) to typecheck against. Defaults to
                        ``{sys.version_info.major}.{sys.version_info.minor}``. This is
                        passed to ``--pythonversion`` in pyright and ``--python-
                        version`` otherwise.
  --no-python-executable
                        Do not infer ``python_executable``
  --no-python-version   Do not infer ``python_version``.
  --venv VENV           Use specified vitualenvironment location
  --infer-venv          Infer virtual environment location. Checks in order environment
                        variables ``VIRTUAL_ENV``, ``CONDA_PREFIX``, directory
                        ``.venv``.
  --constraints CONSTRAINTS
                        Constraints (requirements.txt) specs for checkers. Can specify
                        multiple times. Passed to ``uvx --constraints=...``.
  -v, --verbose         Set verbosity level. Pass multiple times to up level.
  --stdout              logger information to stdout
  --allow-errors        If passed, return ``0`` regardless of checker status.
  --fail-fast           Exit on first failed checker. Default is to run all checkers,
                        even if they fail.
  --dry-run             Perform dry run.
  --no-uvx              If ``--no-uvx`` is passed, assume typecheckers are in the
                        current python environment. Default is to invoke typecheckers
                        using `uvx`.
  --uvx-options UVX_OPTIONS
                        Extra options to pass to ``uvx``. Note that you may have to
                        escape the first option. For example, ``--uvx-options
                        "\--verbose --reinstall"
  --uvx-delimiter UVX_DELIMITER
                        Delimiter between typechecker command arguments and ``uvx``
                        arguments. See ``--check`` option.
```

<!-- [[[end]]] -->
<!-- prettier-ignore-end -->

## Status

This package is actively used by the author. Please feel free to create a pull
request for wanted features and suggestions!

<!-- end-docs -->

## Installation

<!-- start-installation -->

Use one of the following

```bash
pip install typecheck-runner
uv pip install typecheck-runner
uv add typecheck-runner
...
```

<!-- end-installation -->

## What's new?

See [changelog][changelog-link].

## License

This is free software. See [LICENSE][license-link].

## Related work

Any other stuff to mention....

## Contact

The author can be reached at <wpk@nist.gov>.

## Credits

This package was created using
[Cookiecutter](https://github.com/audreyr/cookiecutter) with the
[usnistgov/cookiecutter-nist-python](https://github.com/usnistgov/cookiecutter-nist-python)
template.
