"""Tests for `typecheck-runner` package."""

# pyright: reportUnreachable=false

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def test_version() -> None:
    from typecheck_runner import __version__

    path = Path(__file__).parent.parent / "pyproject.toml"

    with path.open("rb") as f:
        version = tomllib.load(f)["project"]["version"]

    assert version == __version__
