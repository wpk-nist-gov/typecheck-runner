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
    from collections.abc import Generator, Sequence
    from typing import Any


def _pathify(x: str | Path | None) -> Path | None:
    return x if x is None else Path(x)


def _dummy_which(x: str) -> str:
    return "/hello/" + x


def _identity(x: Any) -> Any:
    return x


@pytest.mark.parametrize(
    "verbosity",
    [-1, 0, 1, 2],
)
@pytest.mark.parametrize("stdout", [False, True])
@patch("typecheck_runner.typecheck_runner.logger", autospec=True)
def test__setup_logging(mocked_logger: Any, stdout: bool, verbosity: int) -> None:
    expected = max(0, WARNING - 10 * verbosity)
    typecheck_runner._setup_logging(verbosity, stdout)
    mocked_logger.setLevel.assert_called_once_with(expected)
    mocked_logger.setLevel.assert_called_with(expected)
    assert mocked_logger.setLevel.call_args_list == [
        call(expected),
    ]


def make_fake_venv(
    windows: bool,
    root_path: Path,
    venv: str = ".venv",
) -> None:
    if windows:
        bin_dir = "Scripts"
        exe = "python.exe"
    else:
        bin_dir = "bin"
        exe = "python"

    bin_path = root_path.joinpath(venv, bin_dir)
    bin_path.mkdir(parents=True)

    (bin_path / exe).write_text("hello")


@pytest.fixture
def example_path(tmp_path: Path) -> Generator[Path]:
    old_cwd = Path.cwd()
    os.chdir(tmp_path)

    yield tmp_path

    os.chdir(old_cwd)


@pytest.mark.parametrize(
    ("venv", "environ", "expected"),
    [
        (None, {"VIRTUAL_ENV": "/virtual/env"}, contextlib.nullcontext("/virtual/env")),
        (None, {"CONDA_PREFIX": "/conda/env"}, contextlib.nullcontext("/conda/env")),
        (
            ".venv",
            {"VIRTUAL_ENV": "/virtual/env", "CONDA_PREFIX": "/conda/env"},
            contextlib.nullcontext("/virtual/env"),
        ),
        (
            None,
            {},
            pytest.raises(ValueError, match=r"Could not infer virtual environment.*"),
        ),
        (".venv", {}, contextlib.nullcontext(".venv")),
    ],
)
def test__infer_venv_location(
    example_path: Path, venv: str | None, environ: dict[str, str], expected: Any
) -> None:
    if venv:
        (example_path / venv).mkdir()

    with (
        patch.dict("typecheck_runner.typecheck_runner.os.environ", environ, clear=True),
        expected as e,
    ):
        out = typecheck_runner._infer_venv_location()
        assert out == Path(e).absolute()


venv_marks = pytest.mark.parametrize(
    ("windows", "venv", "location", "expected"),
    [
        (
            False,
            ".venv",
            ".venv",
            contextlib.nullcontext(".venv/bin/python"),
        ),
        (
            False,
            ".venv",
            "venv",
            pytest.raises(ValueError, match=r"No virtual environment.*"),
        ),
        (
            True,
            ".venv",
            ".venv",
            contextlib.nullcontext(".venv/Scripts/python.exe"),
        ),
        (
            False,
            ".nox/test",
            ".nox/test",
            contextlib.nullcontext(".nox/test/bin/python"),
        ),
    ],
)


@venv_marks
def test__get_python_executable_from_venv_no_cd(
    tmp_path: Path, windows: bool, venv: str, location: str, expected: Any
) -> None:
    make_fake_venv(windows, tmp_path, venv)

    path = tmp_path.joinpath(location)

    with (
        (
            patch("typecheck_runner.typecheck_runner.sys.platform", "windows")
            if windows
            else contextlib.nullcontext()
        ),
        expected as e,
    ):
        assert typecheck_runner._get_python_executable_from_venv(
            path
        ) == tmp_path.absolute().joinpath(e)


@venv_marks
def test__get_python_executable_from_venv_cd(
    example_path: Path, windows: bool, venv: str, location: str, expected: Any
) -> None:
    make_fake_venv(windows, example_path, venv)

    path = Path(location)

    with (
        (
            patch("typecheck_runner.typecheck_runner.sys.platform", "windows")
            if windows
            else contextlib.nullcontext()
        ),
        expected as e,
    ):
        assert (
            typecheck_runner._get_python_executable_from_venv(path)
            == Path(e).absolute()
        )


@pytest.mark.parametrize(
    ("python_executable", "venv", "infer_venv", "expected"),
    [
        ("/a/python", ".nox/test", True, ".nox/test/bin/python"),
        ("/a/python", ".venv", False, ".venv/bin/python"),
        ("/a/python", None, False, "/a/python"),
        (None, None, False, None),
        (None, None, True, ".venv/bin/python"),
    ],
)
def test__get_python_executable(
    example_path: Path,
    python_executable: str | None,
    venv: str | None,
    infer_venv: bool,
    expected: str | None,
) -> None:
    make_fake_venv(False, example_path, ".venv")

    if venv is not None and venv != ".venv":
        make_fake_venv(False, example_path, venv)

    with patch.dict("typecheck_runner.typecheck_runner.os.environ", {}, clear=True):
        out = typecheck_runner._get_python_executable(
            _pathify(python_executable), _pathify(venv), infer_venv
        )

        if expected is None:
            assert out is None
        else:
            assert out == Path(expected).absolute()


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
        (sys.executable, False, sys.executable),
        (sys.executable, True, sys.executable),
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
        python_version,
        _pathify(python_executable),
        no_python_version,
        no_python_executable,
    ) == (expected_python_version, _pathify(expected_python_executable))


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
            ["/hello/mypy"],
            id="basic",
        ),
        pytest.param(
            "mypy --verbose -a",
            "mypy",
            ["/hello/mypy", "--verbose", "-a"],
            id="with options",
        ),
        pytest.param(
            "/path/to/mypy",
            "mypy",
            ["/hello//path/to/mypy"],
            id="path",
        ),
        pytest.param(
            "~/mypy",
            "mypy",
            ["/hello/" + str(Path("~/mypy").expanduser())],
            id="expanduser",
        ),
        pytest.param(
            "/path/to/mypy -b --c",
            "mypy",
            ["/hello//path/to/mypy", "-b", "--c"],
            id="path with options",
        ),
        pytest.param(
            "/path/to/ty -b --c",
            "ty",
            ["/hello//path/to/ty", "check", "-b", "--c"],
            id="path with options ty no check",
        ),
    ],
)
@patch("typecheck_runner.typecheck_runner.shutil.which", side_effect=_dummy_which)
def test__parse_command_no_uvx(
    mock_which: Any,  # noqa: ARG001
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
    ("checkers", "args", "expecteds"),
    [
        pytest.param(
            ["mypy"],
            ("--check", "mypy", "--no-uvx", "src"),
            [
                (
                    "/hello/mypy",
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
            ["mypy"],
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
            ["mypy", "pyright"],
            ("--check", "mypy", "--check", "pyright -v", "--no-uvx", "src"),
            [
                (
                    "/hello/mypy",
                    *typecheck_runner._get_python_flags(
                        "mypy",
                        *typecheck_runner._get_python_values(None, None, False, False),
                    ),
                    "src",
                ),
                (
                    "/hello/pyright",
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
@patch("typecheck_runner.typecheck_runner.shutil.which", side_effect=_dummy_which)
def test_main(
    mocked_which: Any,  # noqa: ARG001
    mocked_run_checker: Any,
    checkers: list[str],
    args: Sequence[str],
    expecteds: list[Any],
) -> None:
    assert not typecheck_runner.main(args)
    assert mocked_run_checker.call_args_list == [
        call(*e, dry_run=False) for checker, e in zip(checkers, expecteds, strict=True)
    ]


@pytest.mark.parametrize(
    ("checkers", "args", "expecteds"),
    [
        pytest.param(
            ["mypy", "pyright"],
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
@patch("typecheck_runner.typecheck_runner.shutil.which", side_effect=_identity)
def test_main_fail_fast(
    mocked_which: Any,  # noqa: ARG001
    mocked_run_checker: Any,
    checkers: list[str],
    args: Sequence[str],
    expecteds: list[Any],
    fail_fast: bool,
) -> None:
    out = typecheck_runner.main([*args, *(["--fail-fast"] if fail_fast else [])])

    if fail_fast:
        expecteds = expecteds[:1]
        checkers = checkers[:1]

    expects = expecteds[:1] if fail_fast else expecteds

    assert out == len(expects)
    assert mocked_run_checker.call_args_list == [
        call(*e, dry_run=False) for checker, e in zip(checkers, expecteds, strict=True)
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
