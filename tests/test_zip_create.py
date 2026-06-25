import inspect
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest
import typer

from gulp_cli.commands.ingest import (
    _build_zip_from_sources,
    _expand_source_patterns,
    _safe_archive_name,
    ingest_zip_create,
)
from gulp_cli.config import set_runtime_config_dir


def test_ingest_zip_create_split_size_defaults_to_unset() -> None:
    split_size_default = inspect.signature(ingest_zip_create).parameters[
        "split_size"
    ].default
    assert split_size_default.default is None


def test_ingest_zip_create_no_preserve_path_defaults_to_disabled() -> None:
    no_preserve_path_default = inspect.signature(ingest_zip_create).parameters[
        "no_preserve_path"
    ].default
    assert no_preserve_path_default.default is False


def test_ingest_zip_create_no_overwrite_defaults_to_disabled() -> None:
    no_overwrite_default = inspect.signature(ingest_zip_create).parameters[
        "no_overwrite"
    ].default
    assert no_overwrite_default.default is False


def test_expand_source_patterns_prefers_paths_file(
    tmp_path: Path,
) -> None:
    arg_file = tmp_path / "arg.txt"
    arg_file.write_text("arg", encoding="utf-8")
    file_entry = tmp_path / "from-file.txt"
    file_entry.write_text("from-file", encoding="utf-8")
    paths_file = tmp_path / "paths.txt"
    paths_file.write_text(str(file_entry), encoding="utf-8")

    expanded = _expand_source_patterns([str(arg_file)], str(paths_file))

    assert expanded == [(file_entry.resolve(), file_entry.resolve().parent)]


def test_expand_source_patterns_prints_paths_file_info(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file_entry = tmp_path / "from-file.txt"
    file_entry.write_text("from-file", encoding="utf-8")
    paths_file = tmp_path / "paths.txt"
    paths_file.write_text(f"# comment\n{file_entry}\n", encoding="utf-8")

    _expand_source_patterns([], str(paths_file))

    captured = capsys.readouterr().out
    assert "Reading path list" in captured
    assert str(paths_file.resolve()) in captured
    assert "Loaded" in captured
    assert "1 path expression" in captured


def test_build_zip_from_sources_preserves_path_when_requested(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "samples" / "nested"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "data.json"
    source_file.write_text('{"value": 1}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    output_zip = tmp_path / "out.zip"
    archived_count, archived_entries, created_archives = _build_zip_from_sources(
        output_zip,
        [(source_file, source_dir.parent)],
        preserve_path=True,
    )

    assert archived_count == 1
    assert archived_entries == [_safe_archive_name(str(source_file.resolve()))]
    assert len(created_archives) == 1

    with zipfile.ZipFile(created_archives[0]) as archive:
        assert archive.namelist() == archived_entries


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("./samples/nested/data.json", "samples/nested/data.json"),
        (".\\samples\\nested\\data.json", "samples/nested/data.json"),
        ("../../../samples/nested/data.json", "samples/nested/data.json"),
        ("C:\\samples\\nested\\data.json", "C/samples/nested/data.json"),
        ("\\\\server\\share\\samples\\nested\\data.json", "server/share/samples/nested/data.json"),
    ],
)
def test_safe_archive_name_strips_roots_and_dot_paths(
    path: str, expected: str
) -> None:
    assert _safe_archive_name(path) == expected


def test_build_zip_from_sources_strips_parent_paths_when_preserving(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "samples" / "win_evtx"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "2-system-Microsoft-Windows-LiveId%4Operational.evtx"
    source_file.write_text("payload", encoding="utf-8")
    cwd = tmp_path / "a" / "b" / "c"
    cwd.mkdir(parents=True)
    monkeypatch.chdir(cwd)

    output_zip = tmp_path / "out.zip"
    archived_count, archived_entries, created_archives = _build_zip_from_sources(
        output_zip,
        [(source_file, source_dir.parent)],
        preserve_path=True,
    )

    expected = _safe_archive_name(str(source_file.resolve()))
    assert archived_count == 1
    assert archived_entries == [expected]

    with zipfile.ZipFile(created_archives[0]) as archive:
        assert archive.namelist() == [expected]


def test_build_zip_from_sources_prints_file_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("payload", encoding="utf-8")

    output_zip = tmp_path / "out.zip"
    archived_count, archived_entries, created_archives = _build_zip_from_sources(
        output_zip,
        [(source_file, tmp_path)],
    )

    captured = capsys.readouterr().out
    assert archived_count == 1
    assert archived_entries == ["sample.txt"]
    assert len(created_archives) == 1
    assert "Added" in captured
    assert "sample.txt" in captured
    assert "1/1" in captured
    assert "100%" in captured
    assert "bytes ->" in captured
    assert "GULP_MARKER: [MARKER_FILE_ADDED_TO_ZIP]" in captured
    assert "GULP_MARKER: [MARKER_ZIP_CREATED_SUCCESSFULLY]" in captured


def test_build_zip_from_sources_prints_directory_entries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_dir = tmp_path / "samples"
    nested_dir = source_dir / "nested"
    nested_dir.mkdir(parents=True)
    (nested_dir / "sample.txt").write_text("payload", encoding="utf-8")

    output_zip = tmp_path / "out.zip"
    archived_count, archived_entries, created_archives = _build_zip_from_sources(
        output_zip,
        [(source_dir, tmp_path)],
    )

    captured = capsys.readouterr().out
    assert archived_count == 1
    assert archived_entries == ["samples/nested/", "samples/nested/sample.txt"]
    assert len(created_archives) == 1
    assert "Added" in captured
    assert "samples/nested/" in captured
    assert "samples/nested/sample.txt" in captured
    assert "2/2" in captured
    assert captured.count("GULP_MARKER: [MARKER_FILE_ADDED_TO_ZIP]") == 2

    with zipfile.ZipFile(created_archives[0]) as archive:
        assert archive.namelist() == archived_entries


def test_ingest_zip_create_marks_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("payload", encoding="utf-8")
    output_zip = tmp_path / "out.zip"
    output_zip.write_text("existing", encoding="utf-8")

    with pytest.raises(typer.BadParameter):
        ingest_zip_create(
            str(output_zip),
            [str(source_file)],
            None,
            True,
            False,
            None,
        )

    captured = capsys.readouterr().out
    assert "GULP_MARKER: [MARKER_ZIP_CREATE_ERROR]" in captured
    assert "GULP_MARKER: [MARKER_OTHER_ERROR]" in captured


def test_build_zip_from_sources_uses_config_dir_for_temp_files(
    tmp_path: Path, monkeypatch
) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("payload", encoding="utf-8")
    output_zip = tmp_path / "out.zip"
    config_dir = tmp_path / "config"
    captured: dict[str, Path | None] = {"dir": None}
    original_tempdir = tempfile.TemporaryDirectory

    class _CapturingTemporaryDirectory:
        def __init__(self, *args, **kwargs) -> None:
            temp_dir = kwargs.get("dir")
            captured["dir"] = Path(temp_dir) if temp_dir is not None else None
            self._ctx = original_tempdir(*args, **kwargs)

        def __enter__(self):
            return self._ctx.__enter__()

        def __exit__(self, exc_type, exc, tb):
            return self._ctx.__exit__(exc_type, exc, tb)

    set_runtime_config_dir(config_dir)
    monkeypatch.setattr(
        "gulp_cli.commands.ingest.tempfile.TemporaryDirectory",
        _CapturingTemporaryDirectory,
    )
    try:
        _build_zip_from_sources(output_zip, [(source_file, tmp_path)])
    finally:
        set_runtime_config_dir(None)

    assert captured["dir"] == config_dir.resolve()


def test_build_zip_from_sources_uses_multipart_zip_for_split_size(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if shutil.which("7z") is None:
        pytest.skip("7z is required for multipart ZIP verification")

    source_dir = tmp_path / "samples"
    source_dir.mkdir(parents=True)
    for index in range(3):
        (source_dir / f"file{index}.json").write_bytes(os.urandom(500))

    output_zip = tmp_path / "out.zip"
    archived_count, archived_entries, created_archives = _build_zip_from_sources(
        output_zip,
        [(source_dir, source_dir.parent)],
        split_size_bytes=1_000,
    )

    assert archived_count == 3
    assert len(created_archives) >= 2
    assert archived_entries
    assert "Starting split volume" in capsys.readouterr().out
    assert all(path.name.startswith("out.zip.") for path in created_archives)
    assert all(path.stat().st_size <= 1_000 for path in created_archives)

    extract_dir = tmp_path / "extract_split"
    subprocess.run(
        ["7z", "x", str(created_archives[0]), f"-o{extract_dir}"],
        check=True,
        capture_output=True,
        text=True,
    )
    for index in range(3):
        extracted = extract_dir / "samples" / f"file{index}.json"
        assert extracted.read_bytes() == (source_dir / f"file{index}.json").read_bytes()


def test_build_zip_from_sources_uses_multipart_zip_for_large_entry(
    tmp_path: Path,
) -> None:
    if shutil.which("7z") is None:
        pytest.skip("7z is required for multipart ZIP verification")

    source_file = tmp_path / "big.bin"
    source_file.write_bytes(os.urandom(50_000))
    output_zip = tmp_path / "out.zip"

    archived_count, archived_entries, created_archives = _build_zip_from_sources(
        output_zip,
        [(source_file, tmp_path)],
        split_size_bytes=10 * 1024,
    )

    assert archived_count == 1
    assert archived_entries == ["big.bin"]
    assert [path.name for path in created_archives] == [
        "out.zip.001",
        "out.zip.002",
        "out.zip.003",
        "out.zip.004",
        "out.zip.005",
    ]
    assert all(path.stat().st_size <= 10 * 1024 for path in created_archives)

    extract_dir = tmp_path / "extract"
    subprocess.run(
        ["7z", "x", str(created_archives[0]), f"-o{extract_dir}"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert (extract_dir / "big.bin").read_bytes() == source_file.read_bytes()


def test_build_zip_from_sources_rejects_split_size_above_fat32_limit(
    tmp_path: Path, monkeypatch
) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("payload", encoding="utf-8")
    output_zip = tmp_path / "out.zip"
    monkeypatch.setattr(
        "gulp_cli.commands.ingest._MAX_ZIP_PART_SIZE_BYTES",
        100,
    )

    with pytest.raises(typer.BadParameter, match="4gb"):
        _build_zip_from_sources(
            output_zip,
            [(source_file, tmp_path)],
            split_size_bytes=101,
        )
