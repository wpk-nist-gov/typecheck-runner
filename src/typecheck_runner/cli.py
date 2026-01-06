"""
Interface to type checkers (mypy, (based)pyright, ty, pyrefly) to handle python-version and python-executable.

This allows for running centrally installed (or via uvx) type checkers against a given virtual environment.
"""
# pylint: disable=duplicate-code

from __future__ import annotations

import logging
import os
import shlex
import sys
from argparse import ArgumentParser
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.requirements import Requirement

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


FORMAT = "[%(name)s - %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger("typecheck")


# * Utilities -----------------------------------------------------------------
def _setup_logging(
    verbosity: int = 0,
) -> None:  # pragma: no cover
    """Setup logging."""
    level_number = max(0, logging.WARNING - 10 * verbosity)
    logger.setLevel(level_number)

    # Silence noisy loggers
    logging.getLogger("sh").setLevel(logging.WARNING)


# * Runner --------------------------------------------------------------------
def _do_run(
    *args: str,
    env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> int:
    import subprocess

    cleaned_args = [*(os.fsdecode(arg) for arg in args)]
    full_cmd = shlex.join(cleaned_args)
    logger.info("Running %s", full_cmd)

    if dry_run:
        return 0

    r = subprocess.run(cleaned_args, check=False, env=env)

    if returncode := r.returncode:
        logger.error("Command %s failed with exit code %s", full_cmd, returncode)
        # msg = f"Returned code {returncode}"  # noqa: ERA001
        # raise RuntimeError(msg)  # noqa: ERA001
    return returncode


def _is_pyright_like(checker: str) -> bool:
    return checker in {"pyright", "basedpyright"}


def _get_python_flags(
    checker: str,
    python_version: str,
    python_executable: str,
) -> tuple[str, ...]:
    if checker == "pylint":
        return ()

    if _is_pyright_like(checker):
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

    version_flag = "pythonversion" if _is_pyright_like(checker) else "python-version"

    check_subcommand = ["check"] if checker in {"ty", "pyrefly"} else []

    if checker == "ty":
        # ty prefers `--python` flag pointing to environonmentf
        python_executable = str(Path(python_executable).parent.parent)

    return (
        *check_subcommand,
        f"--{python_flag}={python_executable}",
        f"--{version_flag}={python_version}",
    )


@lru_cache
def _with_parser() -> ArgumentParser:
    parser = ArgumentParser()
    _ = parser.add_argument("-w", "--with", dest="with_args", action="append")
    return parser


def _parse_uvx_command(
    command: str,
    constraints: Sequence[str],
    uvx_options: str,
) -> tuple[str, list[str]]:
    command, *args = shlex.split(command)
    req = Requirement(command)

    with_args, args = _with_parser().parse_known_args(args)

    args = [
        "uvx",
        *shlex.split(uvx_options),
        f"--from={req}",
        *(f"--constraints={c}" for c in constraints),
        *(f"--with={w}" for w in with_args.with_args),
        req.name,
        *args,
    ]
    return req.name, args


def _parse_no_uvx_command(command: str) -> tuple[str, list[str]]:
    command, *args = shlex.split(command)
    path = Path(command).expanduser().absolute()
    return path.name, [str(path), *args]


def _parse_command(
    command: str, no_uv: bool, constraints: Sequence[str], uvx_options: str
) -> tuple[str, list[str]]:
    if no_uv:
        return _parse_no_uvx_command(command)
    return _parse_uvx_command(command, constraints, uvx_options)


def _run_checker(
    checker: str,
    checker_args: Sequence[str],
    extra_args: Sequence[str],
    python_version: str,
    python_executable: str,
    dry_run: bool = False,
) -> int:
    python_flags = _get_python_flags(checker, python_version, python_executable)

    return _do_run(
        *checker_args,
        *python_flags,
        *extra_args,
        dry_run=dry_run,
    )


# * Application ---------------------------------------------------------------
def get_parser() -> ArgumentParser:
    """Get argparser."""
    parser = ArgumentParser(description="Run executable using uvx.")
    _ = parser.add_argument(
        "-c",
        "--check",
        dest="checkers",
        default=[],
        action="append",
        help="""
        Checker to run.  This can be a string with options to the checker.  For example,
        ``--check "mypy --verbose"`` runs the checker the command ``mypy --verbose``.
        Can be specified multiple times.
        """,
    )
    _ = parser.add_argument(
        "--python-executable",
        dest="python_executable",
        default=None,  # Path(sys.executable),
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
        "--constraints",
        dest="constraints",
        default=[],
        action="append",
        type=Path,
        help="""
        Constraints (requirements.txt) specs for checkers.  Can specify multiple times.
        Passed to ``uvx --constraints=...``.
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
        If passed, exit on first failed checker. Default is to run all checkers
        even if they fail.
        """,
    )
    _ = parser.add_argument(
        "--dry-run", action="store_true", help="""Perform dry run."""
    )
    _ = parser.add_argument(
        "--no-uv",
        "--no-uvx",
        dest="no_uvx",
        action="store_true",
        help="""
        If ``--no-uvx`` is passed, assume typecheckers are in the current python environment.
        Default is to invoke typecheckers using `uvx`.
        """,
    )
    _ = parser.add_argument(
        "--uvx-options", default="", help="pass `--verbose` to `uvx`"
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

    _setup_logging(options.verbosity)

    python_version = (
        options.python_version or f"{sys.version_info.major}.{sys.version_info.minor}"
    )
    python_executable = options.python_executable or sys.executable

    logger.debug("checkers: %s", options.checkers)
    logger.debug("args: %s", options.args)

    code = 0
    for command in options.checkers:
        checker, args = _parse_command(
            command,
            no_uv=options.no_uv,
            constraints=options.constraints,
            uvx_options=options.uvx_options,
        )
        checker_code = _run_checker(
            checker,
            args,
            options.args,
            python_version=python_version,
            python_executable=python_executable,
            dry_run=options.dry_run,
        )
        if options.fail_fast and checker_code != 0:
            return checker_code

        code += checker_code

    return 0 if options.allow_errors else code
