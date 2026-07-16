from pathlib import Path

from typer.testing import CliRunner

import gulp_cli.cli as cli


def test_command_prints_elapsed_time_last(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("payload", encoding="utf-8")
    ticks = iter((10.0, 11.234))
    monkeypatch.setattr(cli, "perf_counter", lambda: next(ticks))

    result = CliRunner().invoke(
        cli.app,
        ["ingest", "zip-create", str(tmp_path / "out.zip"), str(source)],
    )

    assert result.exit_code == 0
    assert result.stdout.rstrip().endswith("Elapsed time: 1.23s")
