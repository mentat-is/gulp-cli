"""Default behavior for ``query raw`` without ``--q``."""

from typer.testing import CliRunner


def test_query_raw_without_q_runs_match_all_preview(monkeypatch) -> None:
    import gulp_cli.commands.query as query

    calls: list[dict] = []

    class _Queries:
        async def query_raw(self, **kwargs):
            calls.append(kwargs)
            return {"data": {"docs": []}}

    class _Client:
        queries = _Queries()

    class _GetClient:
        async def __aenter__(self):
            return _Client()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(query, "get_client", _GetClient)
    monkeypatch.setattr(query, "print_result", lambda _result: None)

    result = CliRunner().invoke(query.app, ["raw", "test_operation"])

    print("query raw default SDK call:", calls)
    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "operation_id": "test_operation",
            "q": {"query": {"match_all": {}}},
            "q_options": {"preview_mode": True},
            "wait": False,
        }
    ]
