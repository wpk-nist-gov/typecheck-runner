"""
Interface to type checkers (mypy, (based)pyright, ty, pyrefly).

This handles locating python-version and python-executable. This allows for
running centrally installed (or via uvx) type checkers against a given virtual
environment.
"""
# pylint: disable=duplicate-code

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from packaging.requirements import Requirement

if TYPE_CHECKING:
    from collections.abc import Sequence
    from logging import Logger


FORMAT = "[typecheck-runner %(levelname)s] %(message)s"
logger: Logger = logging.getLogger(__name__)


# * Utilities -----------------------------------------------------------------
def _setup_logging(
    verbosity: int = 0,
    stdout: bool = False,
) -> None:  # pragma: no cover
    """Setup logging."""
    level_number = max(0, logging.WARNING - 10 * verbosity)
    logger.setLevel(level_number)

    # Silence noisy loggers
    logging.getLogger("sh").setLevel(logging.WARNING)

    if stdout:
        handler = logging.StreamHandler(sys.stdout)
        logging.basicConfig(level=logging.WARNING, format=FORMAT, handlers=[handler])
    else:
        logging.basicConfig(level=logging.WARNING, format=FORMAT)


# * Runner --------------------------------------------------------------------


def _infer_venv_location() -> Path:
    for var in ("VIRTUAL_ENV", "CONDA_PREFIX"):
        if venv := os.getenv(var, ""):
            logger.debug("Inferred venv location %s", venv)
            return Path(venv).absolute()

    for d in (".venv",):
        if (path := Path(d)).is_dir():
            logger.debug("Inferred venv location %s", path)
            return path.absolute()

    msg = "Could not infer virtual environment"
    raise ValueError(msg)


def _get_python_executable_from_venv(
    location: Path,
) -> Path:
    executable = "python.exe" if sys.platform.startswith("win") else "python"
    for d in ("bin", "Scripts"):
        if (path := location / d / executable).exists():
            logger.debug("Inferred python-executable %s", path)
            return path.absolute()

    msg = f"No virtual environment found under {location}"
    raise ValueError(msg)


def _get_python_executable(
    python_executable: Path | None, venv: Path | None, infer_venv: bool
) -> Path | None:
    if venv is None and infer_venv:
        venv = _infer_venv_location()

    if venv is not None:
        return _get_python_executable_from_venv(venv)

    return python_executable


def _get_python_values(
    python_version: str | None,
    python_executable: Path | None,
    no_python_version: bool,
    no_python_executable: bool,
) -> tuple[str | None, Path | None]:
    if python_version is None and not no_python_version:
        if python_executable is not None:
            # infer python version from python_executable
            logger.debug(
                "Calculate python-version from executable %s", python_executable
            )
            script = "import sys; info = sys.version_info; print(f'{info.major}.{info.minor}')"
            python_version = (
                subprocess.check_output([python_executable, "-c", script])
                .decode("utf-8")
                .strip()
            )
        else:
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    if python_executable is None and not no_python_executable:
        python_executable = Path(sys.executable)

    return python_version, python_executable


def _maybe_add_check_argument(checker: str, args: list[str]) -> list[str]:
    if checker in {"ty", "pyrefly"} and "check" not in args:
        return ["check", *args]
    return args


def _parse_command(
    command: str,
    no_uvx: bool,
    uvx_delimiter: str,
    uvx_options: Sequence[str],
) -> tuple[str, list[str]]:
    command, *args = shlex.split(command)

    if no_uvx:
        path = Path(command).expanduser()
        checker = path.name
        path_str = str(path)
        return checker, [
            shutil.which(path_str) or path_str,
            *_maybe_add_check_argument(checker, args),
        ]

    req = Requirement(command)
    checker = req.name

    idx = args.index(uvx_delimiter) if uvx_delimiter in args else len(args)
    checker_args = args[:idx]
    uvx_args = args[idx + 1 :]

    args = [
        "uvx",
        *uvx_options,
        *uvx_args,
        command,
        *_maybe_add_check_argument(checker, checker_args),
    ]
    return checker, args


PYRIGHT_LIKE_CHECKERS = {"pyright", "basedpyright"}


def _get_python_flags(
    checker: str,
    python_version: str | None,
    python_executable: str | Path | None,
) -> list[str]:
    out: list[str] = []
    if python_version is not None:
        version_flag = (
            "pythonversion" if checker in PYRIGHT_LIKE_CHECKERS else "python-version"
        )
        out.append(f"--{version_flag}={python_version}")

    if python_executable is not None:
        if checker in PYRIGHT_LIKE_CHECKERS:
            python_flag = "pythonpath"
        elif checker == "ty":
            python_flag = "python"
        elif checker == "pyrefly":
            python_flag = "python-interpreter-path"
        elif checker == "mypy":
            # default to mypy
            python_flag = "python-executable"
        else:
            msg = f"Unknown checker {checker}"
            raise ValueError(msg)
        out.append(f"--{python_flag}={python_executable}")

    return out


def _run_checker(
    *args: str,
    dry_run: bool = False,
) -> int:
    cleaned_args = [os.fsdecode(arg) for arg in args]
    full_cmd = shlex.join(cleaned_args)
    logger.info("Command: %s", full_cmd)

    if dry_run:
        return 0

    start_time = perf_counter()
    returncode = subprocess.call(cleaned_args)
    logger.info("Execution time: %s", perf_counter() - start_time)
    if returncode:
        logger.error("Failed with exit code: %s", returncode)

    return returncode


# * Application ---------------------------------------------------------------
def get_parser() -> ArgumentParser:
    """Get argparser."""
    parser = ArgumentParser(description="Run executable using uvx.")
    _ = parser.add_argument("--version", action="store_true", help="Display version.")

    _ = parser.add_argument(
        "-c",
        "--check",
        dest="checkers",
        default=[],
        action="append",
        help="""
        Checker to run. This can be a string with options to the checker. For
        example, ``--check "mypy --verbose"`` runs the checker the command
        ``mypy --verbose``. Options after ``uvx_delimiter`` (default ``"--"``,
        see ``--uvx-delimiter`` options) are treated as ``uvx`` options. For
        example, passing ``--check "mypy --verbose -- --reinstall"`` will run
        ``uvx --reinstall mypy --verbose``. Can be specified multiple times.
        """,
    )
    _ = parser.add_argument(
        "--python-executable",
        dest="python_executable",
        default=None,
        type=Path,
        help="""
        Path to python executable. Defaults to ``sys.executable``. This is
        passed to ``--python-executable`` (mypy), ``--pythonpath`` in
        ((based)pyright), ``--python`` (ty), ``--python-interpreter-path``
        (pyrefly), and ignored for pylint.
        """,
    )
    _ = parser.add_argument(
        "--python-version",
        dest="python_version",
        default=None,
        type=str,
        help="""
        Python version (x.y) to typecheck against. Defaults to
        ``{sys.version_info.major}.{sys.version_info.minor}``. This is passed
        to ``--pythonversion`` in pyright and ``--python-version`` otherwise.
        """,
    )
    _ = parser.add_argument(
        "--no-python-executable",
        action="store_true",
        help="""
        Do not infer ``python_executable``
        """,
    )
    _ = parser.add_argument(
        "--no-python-version",
        action="store_true",
        help="""
        Do not infer ``python_version``.
        """,
    )

    _ = parser.add_argument(
        "--venv",
        type=Path,
        help="""
        Use specified vitualenvironment location
        """,
    )
    _ = parser.add_argument(
        "--infer-venv",
        action="store_true",
        help="""
        Infer virtual environment location.  Checks in order environment variables ``VIRTUAL_ENV``, ``CONDA_PREFIX``, directory ``.venv``.
        """,
    )
    _ = parser.add_argument(
        "--constraints",
        dest="constraints",
        default=[],
        action="append",
        type=Path,
        help="""
        Constraints (requirements.txt) specs for checkers. Can specify multiple
        times. Passed to ``uvx --constraints=...``.
        """,
    )
    _ = parser.add_argument(
        "-v",
        "--verbose",
        dest="verbosity",
        action="count",
        default=0,
        help="Set verbosity level.  Pass multiple times to up level.",
    )
    _ = parser.add_argument(
        "--stdout", action="store_true", help="logger information to stdout"
    )
    _ = parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="""
        If passed, return ``0`` regardless of checker status.
        """,
    )
    _ = parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="""
        Exit on first failed checker. Default is to run all checkers, even if
        they fail.
        """,
    )
    _ = parser.add_argument(
        "--dry-run", action="store_true", help="""Perform dry run."""
    )
    _ = parser.add_argument(
        "--no-uvx",
        dest="no_uvx",
        action="store_true",
        help="""
        If ``--no-uvx`` is passed, assume typecheckers are in the current
        python environment. Default is to invoke typecheckers using `uvx`.
        """,
    )
    _ = parser.add_argument(
        "--uvx-options",
        default="",
        help="""
        Extra options to pass to ``uvx``. Note that you may have to escape the
        first option. For example, ``--uvx-options "\\--verbose --reinstall"
        """,
    )
    _ = parser.add_argument(
        "--uvx-delimiter",
        default="--",
        help="""
        Delimiter between typechecker command arguments and ``uvx`` arguments.
        See ``--check`` option.
        """,
    )
    _ = parser.add_argument(
        "args",
        type=str,
        nargs="*",
        default=[],
        help="Extra files/arguments passed to all checkers.",
    )

    return parser


def main(args: Sequence[str] | None = None) -> int:
    """Main script."""
    parser = get_parser()
    options = parser.parse_args(args)

    if options.version:
        from typecheck_runner import __version__

        print("typecheck-runner", __version__)  # noqa: T201
        return 0

    if not options.checkers:
        parser.print_help()
        return 2

    _setup_logging(options.verbosity, options.stdout)

    # possibly infer python executable from location
    python_version, python_executable = _get_python_values(
        python_version=options.python_version,
        python_executable=_get_python_executable(
            options.python_executable, options.venv, options.infer_venv
        ),
        no_python_version=options.no_python_version,
        no_python_executable=options.no_python_executable,
    )

    logger.info("python_executable %s", python_executable)
    logger.info("python_version %s", python_version)
    logger.debug("checkers: %s", options.checkers)
    logger.debug("args: %s", options.args)

    uvx_options = [
        *shlex.split(options.uvx_options),
        *(f"--constraints={c}" for c in options.constraints),
    ]

    code = 0
    for command in options.checkers:
        checker, args = _parse_command(
            command,
            no_uvx=options.no_uvx,
            uvx_delimiter=options.uvx_delimiter,
            uvx_options=uvx_options,
        )
        logger.info("Checker: %s", checker)
        checker_code = _run_checker(
            *args,
            *_get_python_flags(checker, python_version, python_executable),
            *options.args,
            dry_run=options.dry_run,
        )
        if options.fail_fast and checker_code:
            return checker_code

        code += checker_code

    return 0 if options.allow_errors else code


if __name__ == "__main__":
    raise SystemExit(main())
