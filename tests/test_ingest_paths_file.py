from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import typer

from gulp_cli.commands.ingest import (
    _expand_source_patterns,
    ingest_file_to_source,
    ingest_file,
)


def test_ingest_file_paths_file_option_defaults_to_unset() -> None:
    paths_file_default = inspect.signature(ingest_file).parameters["paths_file"].default
    assert paths_file_default.default is None


def test_ingest_file_to_source_paths_file_option_defaults_to_unset() -> None:
    paths_file_default = inspect.signature(ingest_file_to_source).parameters[
        "paths_file"
    ].default
    assert paths_file_default.default is None


def test_expand_source_patterns_supports_ingest_paths_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arg_file = tmp_path / "arg.txt"
    arg_file.write_text("arg", encoding="utf-8")
    file_entry = tmp_path / "from-file.txt"
    file_entry.write_text("from-file", encoding="utf-8")
    paths_file = tmp_path / "paths.txt"
    paths_file.write_text(f"# comment\n{file_entry}\n", encoding="utf-8")

    expanded = [
        str(path)
        for path, _base_dir in _expand_source_patterns(
            [str(arg_file)], str(paths_file)
        )
    ]

    out = capsys.readouterr().out
    assert expanded == [str(file_entry.resolve())]
    assert "Reading path list" in out
    assert "Ignoring positional path patterns" in out
    assert "Loaded" in out


def test_expand_source_patterns_requires_input() -> None:
    with pytest.raises(typer.BadParameter, match="Provide at least one path argument"):
        _expand_source_patterns([], None)


def test_expand_source_patterns_rejects_binary_paths_file(tmp_path: Path) -> None:
    paths_file = tmp_path / "binary.evtx"
    paths_file.write_bytes(b"\x80\x81not-text")

    with pytest.raises(typer.BadParameter, match="must be UTF-8 text"):
        _expand_source_patterns([], str(paths_file))
