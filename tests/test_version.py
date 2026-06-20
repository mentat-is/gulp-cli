from __future__ import annotations

import gulp_cli._version as build_version
import gulp_cli.version as version_module


def test_print_version_prints_cli_version_only(capsys, monkeypatch) -> None:
    monkeypatch.setattr(build_version, "__version__", "1.2.3")
    monkeypatch.setattr(build_version, "__commit_id__", "deadbeef")

    version_module.print_version()

    out = capsys.readouterr().out
    assert "gulp-cli version: 1.2.3 (deadbeef)" in out


def test_utility_gulp_version_command_uses_client_version(capsys, monkeypatch) -> None:
    import gulp_cli.commands.utility as utility

    seen = {}

    class _FakeClient:
        async def version(self, *, req_id: str | None = None) -> str:
            seen["req_id"] = req_id
            return "9.8.7"

    class _FakeGetClient:
        def __init__(self, client):
            self.client = client

        async def __aenter__(self):
            return self.client

        async def __aexit__(self, exc_type, exc, tb):
            return None

    def _fake_get_client():
        seen["called"] = True
        return _FakeGetClient(_FakeClient())

    monkeypatch.setattr(utility, "get_client", _fake_get_client)

    utility.utility_gulp_version()

    out = capsys.readouterr().out
    assert out.strip() == "9.8.7"
    assert seen["called"] is True
    assert seen["req_id"] is None
