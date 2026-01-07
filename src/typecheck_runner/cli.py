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
import sys
from argparse import ArgumentParser
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


def _get_python_values(
    python_version: str | None,
    python_executable: str | None,
    no_python_version: bool,
    no_python_executable: bool,
) -> tuple[str | None, str | None]:
    if python_version is None and not no_python_version:
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    if python_executable is None and not no_python_executable:
        python_executable = sys.executable

    return python_version, python_executable


def _parse_uvx_command(
    command: str,
    constraints: Sequence[str],
    uvx_delimiter: str,
    uvx_options: str,
) -> tuple[str, list[str]]:
    command, *args = shlex.split(command)
    req = Requirement(command)

    idx = args.index(uvx_delimiter) if uvx_delimiter in args else len(args)
    checker_args = args[:idx]
    uvx_args = args[idx + 1 :]

    args = [
        "uvx",
        *shlex.split(uvx_options),
        *uvx_args,
        *(f"--constraints={c}" for c in constraints),
        command,
        *checker_args,
    ]
    return req.name, args


def _parse_no_uvx_command(command: str) -> tuple[str, list[str]]:
    command, *args = shlex.split(command)
    path = Path(command).expanduser().absolute()
    return path.name, [str(path), *args]


def _parse_command(
    command: str,
    no_uvx: bool,
    constraints: Sequence[str],
    uvx_delimiter: str,
    uvx_options: str,
) -> tuple[str, list[str]]:
    if no_uvx:
        return _parse_no_uvx_command(command)
    return _parse_uvx_command(
        command,
        constraints=constraints,
        uvx_delimiter=uvx_delimiter,
        uvx_options=uvx_options,
    )


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


PYRIGHT_LIKE_CHECKERS = {"pyright", "basedpyright"}


def _get_python_flags(
    checker: str,
    python_version: str | None,
    python_executable: str | None,
) -> list[str]:
    if checker == "pylint":
        return []

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
    checker: str,
    checker_args: Sequence[str],
    extra_args: Sequence[str],
    python_version: str | None,
    python_executable: str | None,
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
        delimiter between typechecker command arguments and ``uvx`` arguments.
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

    _setup_logging(options.verbosity)

    python_version, python_executable = _get_python_values(
        python_version=options.python_version,
        python_executable=options.python_executable,
        no_python_version=options.no_python_version,
        no_python_executable=options.no_python_executable,
    )

    logger.debug("checkers: %s", options.checkers)
    logger.debug("args: %s", options.args)

    code = 0
    for command in options.checkers:
        checker, args = _parse_command(
            command,
            no_uvx=options.no_uvx,
            constraints=options.constraints,
            uvx_delimiter=options.uvx_delimiter,
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


if __name__ == "__main__":
    raise SystemExit(main())
