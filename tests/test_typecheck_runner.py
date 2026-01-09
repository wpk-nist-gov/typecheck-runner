# ruff: noqa: SLF001
# pylint: disable=protected-access,use-implicit-booleaness-not-comparison-to-zero
from __future__ import annotations

import contextlib
import os
import sys
from logging import WARNING
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import call, patch

import pytest

from typecheck_runner import typecheck_runner

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any


@pytest.mark.parametrize(
    "verbosity",
    [-1, 0, 1, 2],
)
@patch("typecheck_runner.typecheck_runner.logger", autospec=True)
def test__setup_logging(mocked_logger: Any, verbosity: int) -> None:
    expected = max(0, WARNING - 10 * verbosity)
    typecheck_runner._setup_logging(verbosity)
    mocked_logger.setLevel.assert_called_once_with(expected)
    mocked_logger.setLevel.assert_called_with(expected)
    assert mocked_logger.setLevel.call_args_list == [
        call(expected),
    ]


@pytest.mark.parametrize(
    ("python_version", "no_python_version", "expected_python_version"),
    [
        (None, False, "infer"),
        (None, True, None),
        ("3.2", False, "3.2"),
        ("3.2", True, "3.2"),
    ],
)
@pytest.mark.parametrize(
    ("python_executable", "no_python_executable", "expected_python_executable"),
    [
        (None, False, "infer"),
        (None, True, None),
        ("/path/to/python", False, "/path/to/python"),
        ("/path/to/python", True, "/path/to/python"),
    ],
)
def test__get_python_values(
    python_version: str | None,
    no_python_version: bool,
    expected_python_version: str | None,
    python_executable: str | None,
    no_python_executable: bool,
    expected_python_executable: str | None,
) -> None:
    if expected_python_version == "infer":
        expected_python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    if expected_python_executable == "infer":
        expected_python_executable = sys.executable

    assert typecheck_runner._get_python_values(
        python_version, python_executable, no_python_version, no_python_executable
    ) == (expected_python_version, expected_python_executable)


@pytest.mark.parametrize(
    ("checker", "args", "expected"),
    [
        ("mypy", ["a", "b", "c"], ["a", "b", "c"]),
        ("ty", ["a", "b", "c"], ["check", "a", "b", "c"]),
        ("ty", ["check", "a", "b", "c"], ["check", "a", "b", "c"]),
        ("pyrefly", ["--verbose"], ["check", "--verbose"]),
        ("pyrefly", ["--verbose", "check"], ["--verbose", "check"]),
    ],
)
def test__maybe_add_check_argument(
    checker: str, args: list[str], expected: list[str]
) -> None:
    assert typecheck_runner._maybe_add_check_argument(checker, args) == expected


@pytest.mark.parametrize(
    ("command", "uvx_delimiter", "uvx_options", "expected_command", "expected_args"),
    [
        pytest.param(
            "mypy",
            None,
            [],
            "mypy",
            ["uvx", "mypy"],
            id="basic",
        ),
        pytest.param(
            "mypy",
            None,
            ["--verbose"],
            "mypy",
            ["uvx", "--verbose", "mypy"],
            id="with uvx_options",
        ),
        pytest.param(
            "mypy --verbose -a -b",
            None,
            [],
            "mypy",
            ["uvx", "mypy", "--verbose", "-a", "-b"],
            id="with checker options",
        ),
        pytest.param(
            "mypy -- --from mypy[faster-cache]",
            "--",
            [],
            "mypy",
            ["uvx", "--from", "mypy[faster-cache]", "mypy"],
            id="with checker uvx options",
        ),
        pytest.param(
            "mypy ;; --from mypy[faster-cache]",
            ";;",
            ["--verbose"],
            "mypy",
            ["uvx", "--verbose", "--from", "mypy[faster-cache]", "mypy"],
            id="with checker uvx options delimiter",
        ),
        pytest.param(
            "mypy[faster-cache] -a",
            None,
            ["--verbose"],
            "mypy",
            ["uvx", "--verbose", "mypy[faster-cache]", "-a"],
            id="with optional extras",
        ),
        pytest.param(
            "ty -a",
            None,
            ["--verbose"],
            "ty",
            ["uvx", "--verbose", "ty", "check", "-a"],
            id="with optional extras add check",
        ),
    ],
)
def test__parser_command_uvx(
    command: str,
    uvx_delimiter: str,
    uvx_options: Sequence[str],
    expected_command: str,
    expected_args: list[str],
) -> None:
    assert typecheck_runner._parse_command(
        command, False, uvx_delimiter, uvx_options
    ) == (expected_command, expected_args)


@pytest.mark.parametrize(
    ("command", "expected_command", "expected_args"),
    [
        pytest.param(
            "mypy",
            "mypy",
            ["mypy"],
            id="basic",
        ),
        pytest.param(
            "mypy --verbose -a",
            "mypy",
            ["mypy", "--verbose", "-a"],
            id="with options",
        ),
        pytest.param(
            "/path/to/mypy",
            "mypy",
            ["/path/to/mypy"],
            id="path",
        ),
        pytest.param(
            "~/mypy",
            "mypy",
            [str(Path("~/mypy").expanduser())],
            id="expanduser",
        ),
        pytest.param(
            "/path/to/mypy -b --c",
            "mypy",
            ["/path/to/mypy", "-b", "--c"],
            id="path with options",
        ),
        pytest.param(
            "/path/to/ty -b --c",
            "ty",
            ["/path/to/ty", "check", "-b", "--c"],
            id="path with options ty no check",
        ),
    ],
)
def test__parse_command_no_uvx(
    command: str,
    expected_command: str,
    expected_args: list[str],
) -> None:
    assert typecheck_runner._parse_command(command, True, "", []) == (
        expected_command,
        expected_args,
    )


@pytest.mark.parametrize(
    ("checker", "version_flag", "python_flag"),
    [
        ("mypy", "python-version", "python-executable"),
        ("pyright", "pythonversion", "pythonpath"),
        ("basedpyright", "pythonversion", "pythonpath"),
        ("ty", "python-version", "python"),
        ("pyrefly", "python-version", "python-interpreter-path"),
    ],
)
@pytest.mark.parametrize("python_version", [None, "3.8"])
@pytest.mark.parametrize("python_executable", [None, "/path/to/python"])
def test__get_python_flags(
    checker: str,
    version_flag: str,
    python_flag: str,
    python_version: str | None,
    python_executable: str | None,
) -> None:
    expected: list[str] = []
    if python_version:
        expected.append(f"--{version_flag}={python_version}")

    if python_executable:
        expected.append(f"--{python_flag}={python_executable}")

    assert (
        typecheck_runner._get_python_flags(checker, python_version, python_executable)
        == expected
    )


def test__get_python_flags_bad_checker() -> None:
    with pytest.raises(ValueError, match=r"Unknown checker .*"):
        _ = typecheck_runner._get_python_flags("other", "", "")


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(
            ("mypy", "--verbose"),
            id="basic",
        ),
        pytest.param(
            ("uvx", "--verbose", "mypy", "--verbose", "src"),
            id="more",
        ),
    ],
)
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("return_value", [0, 10])
@patch("typecheck_runner.typecheck_runner.logger", autospec=True)
def test__run_checker(
    mocked_logger: Any,
    args: str,
    dry_run: bool,
    return_value: int,
) -> None:
    expected = 0 if dry_run else return_value

    with patch(
        "typecheck_runner.typecheck_runner.subprocess.call",
        autospec=True,
        return_value=return_value,
    ) as mocked_call:
        assert typecheck_runner._run_checker(*args, dry_run=dry_run) == expected
        assert (
            mocked_logger.error.call_count == 0 if (dry_run or not return_value) else 1
        )

        if dry_run:
            assert mocked_call.call_args_list == []
        else:
            mocked_call.assert_called_once_with([os.fsdecode(arg) for arg in args])


@pytest.mark.parametrize(
    ("args", "expecteds"),
    [
        pytest.param(
            ("--check", "mypy", "--no-uvx", "src"),
            [
                (
                    "mypy",
                    *typecheck_runner._get_python_flags(
                        "mypy",
                        *typecheck_runner._get_python_values(None, None, False, False),
                    ),
                    "src",
                )
            ],
            id="no_uvx",
        ),
        pytest.param(
            ("--check", "mypy --verbose", "src"),
            [
                (
                    "uvx",
                    "mypy",
                    "--verbose",
                    *typecheck_runner._get_python_flags(
                        "mypy",
                        *typecheck_runner._get_python_values(None, None, False, False),
                    ),
                    "src",
                )
            ],
            id="uvx",
        ),
        pytest.param(
            ("--check", "mypy", "--check", "pyright -v", "--no-uvx", "src"),
            [
                (
                    "mypy",
                    *typecheck_runner._get_python_flags(
                        "mypy",
                        *typecheck_runner._get_python_values(None, None, False, False),
                    ),
                    "src",
                ),
                (
                    "pyright",
                    "-v",
                    *typecheck_runner._get_python_flags(
                        "pyright",
                        *typecheck_runner._get_python_values(None, None, False, False),
                    ),
                    "src",
                ),
            ],
            id="mult",
        ),
    ],
)
@patch("typecheck_runner.typecheck_runner._run_checker", autospec=True, return_value=0)
def test_main(
    mocked_run_checker: Any,
    args: Sequence[str],
    expecteds: list[Any],
) -> None:
    assert not typecheck_runner.main(args)
    assert mocked_run_checker.call_args_list == [
        call(*e, dry_run=False) for e in expecteds
    ]


@pytest.mark.parametrize(
    ("args", "expecteds"),
    [
        pytest.param(
            ("--check", "mypy", "--check", "pyright -v", "--no-uvx", "src"),
            [
                (
                    "mypy",
                    *typecheck_runner._get_python_flags(
                        "mypy",
                        *typecheck_runner._get_python_values(None, None, False, False),
                    ),
                    "src",
                ),
                (
                    "pyright",
                    "-v",
                    *typecheck_runner._get_python_flags(
                        "pyright",
                        *typecheck_runner._get_python_values(None, None, False, False),
                    ),
                    "src",
                ),
            ],
            id="mult",
        ),
    ],
)
@pytest.mark.parametrize("fail_fast", [False, True])
@patch("typecheck_runner.typecheck_runner._run_checker", autospec=True, return_value=1)
def test_main_fail_fast(
    mocked_run_checker: Any,
    args: Sequence[str],
    expecteds: list[Any],
    fail_fast: bool,
) -> None:
    out = typecheck_runner.main([*args, *(["--fail-fast"] if fail_fast else [])])

    expects = expecteds[:1] if fail_fast else expecteds

    assert out == len(expects)
    assert mocked_run_checker.call_args_list == [
        call(*e, dry_run=False) for e in expects
    ]


@patch("typecheck_runner.typecheck_runner._run_checker", autospec=True)
def test_main_help(
    mocked_run_checker: Any,
) -> None:
    assert typecheck_runner.main([]) == 2  # noqa: PLR2004
    assert mocked_run_checker.call_args_list == []


@patch("typecheck_runner.typecheck_runner.print")
def test_main_version(mocked_print: Any) -> None:
    from typecheck_runner import __version__

    assert typecheck_runner.main(["--version"]) == 0
    mocked_print.assert_called_once_with("typecheck-runner", __version__)


@patch("typecheck_runner.typecheck_runner.main", return_value=0)
def test__main__(mocked_main: Any) -> None:
    with contextlib.suppress(SystemExit):
        import typecheck_runner.__main__  # noqa: F401

        mocked_main.assert_called_once_with()
