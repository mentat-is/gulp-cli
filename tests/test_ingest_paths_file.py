from __future__ import annotations

import inspect
import bz2
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from gulp_cli.commands import ingest as ingest_module
from gulp_cli.commands.ingest import (
    _expand_source_patterns,
    _maybe_bz2_compress_file_for_ingestion,
    _plugin_params_request_compression,
    ingest_file_to_source,
    ingest_file,
)


def test_ingest_file_assigns_a_distinct_req_id_to_each_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = [tmp_path / "one.log", tmp_path / "two.log"]
    for path in files:
        path.write_text("event", encoding="utf-8")

    req_ids: list[str] = []

    class _Ingest:
        async def file(self, **kwargs):
            req_id = kwargs["params"]["req_id"]
            req_ids.append(req_id)
            return SimpleNamespace(req_id=req_id, status="pending")

    class _Client:
        ingest = _Ingest()

        async def ensure_websocket(self) -> None:
            return None

    class _ClientContext:
        async def __aenter__(self):
            return _Client()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _Tracker:
        @classmethod
        async def create(cls, *_args, **_kwargs):
            return cls()

        async def wait_for_confirm(self, _req_id: str, _timeout: float) -> bool:
            return False

        def close(self) -> None:
            return None

    async def _operation_exists(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(ingest_module, "get_client", lambda: _ClientContext())
    monkeypatch.setattr(ingest_module, "_IngestWsTracker", _Tracker)
    monkeypatch.setattr(ingest_module, "_ensure_operation_exists", _operation_exists)
    monkeypatch.setattr(ingest_module, "print_result", lambda _result: None)

    ingest_file(
        operation_id="op",
        plugin="raw",
        file_patterns=[str(path) for path in files],
        paths_file=None,
        context_name="ctx",
        plugin_params=None,
        flt=None,
        reset_operation=False,
        create_operation_if_missing=False,
        preview=False,
        wait=False,
        wait_log=False,
        wait_timeout=300,
        show_per_file_progress=False,
        batch_size=2,
    )

    assert len(req_ids) == len(files)
    assert len(set(req_ids)) == len(files)


def test_ingest_file_paths_file_option_defaults_to_unset() -> None:
    paths_file_default = inspect.signature(ingest_file).parameters["paths_file"].default
    assert paths_file_default.default is None


def test_ingest_file_patterns_argument_defaults_to_unset() -> None:
    file_patterns_default = inspect.signature(ingest_file).parameters[
        "file_patterns"
    ].default
    assert file_patterns_default.default is None
    assert "--paths-file" in file_patterns_default.help


def test_ingest_file_to_source_paths_file_option_defaults_to_unset() -> None:
    paths_file_default = inspect.signature(ingest_file_to_source).parameters[
        "paths_file"
    ].default
    assert paths_file_default.default is None


def test_ingest_file_to_source_patterns_argument_defaults_to_unset() -> None:
    file_patterns_default = inspect.signature(ingest_file_to_source).parameters[
        "file_patterns"
    ].default
    assert file_patterns_default.default is None
    assert "--paths-file" in file_patterns_default.help


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


def test_compressed_plugin_params_create_bz2_upload_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.evtx"
    payload = b"event log bytes"
    source.write_bytes(payload)

    assert _plugin_params_request_compression({"compressed": True})
    upload_path, temp_path = asyncio.run(
        _maybe_bz2_compress_file_for_ingestion(
            str(source), {"compressed": True}
        )
    )
    try:
        assert temp_path == upload_path
        assert upload_path.endswith(".bz2")
        with bz2.open(upload_path, "rb") as f:
            assert f.read() == payload
    finally:
        Path(upload_path).unlink(missing_ok=True)


def test_uncompressed_plugin_params_keep_original_upload_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.evtx"
    source.write_bytes(b"event log bytes")

    assert not _plugin_params_request_compression({})
    upload_path, temp_path = asyncio.run(
        _maybe_bz2_compress_file_for_ingestion(str(source), {})
    )

    assert upload_path == str(source)
    assert temp_path is None
