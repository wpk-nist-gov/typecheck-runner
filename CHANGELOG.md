<!-- markdownlint-disable MD024 -->
<!-- markdownlint-disable MD013 -->
<!-- prettier-ignore-start -->
# Changelog

Changelog for `typecheck-runner`

## Unreleased

[changelog.d]: https://github.com/wpk-nist-gov/typecheck-runner/tree/main/changelog.d

See the fragment files in [changelog.d]
<!-- prettier-ignore-end -->

<!-- markdownlint-enable MD013 -->

<!-- scriv-insert-here -->

## 0.1.1 — 2026-01-14

### Added

- Added `--stdout` option to force logging info to stdout

### Changed

- Checkers with `--no-uvx` are now expanded to full path using `shutil.which`.
