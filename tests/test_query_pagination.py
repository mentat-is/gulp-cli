"""CLI coverage for offset and PIT raw pagination."""

from typer.testing import CliRunner


def _install_query_client(monkeypatch, query_module):
    calls: list[tuple[str, dict]] = []

    class _Queries:
        async def query_raw_paginate(self, **kwargs):
            calls.append(("paginate", kwargs))
            return {"total_hits": 0, "docs": [], "pit_id": "pit-new"}

        async def query_raw_paginate_close(self, **kwargs):
            calls.append(("close", kwargs))
            return {"closed": True}

    class _Client:
        queries = _Queries()

    class _GetClient:
        async def __aenter__(self):
            return _Client()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(query_module, "get_client", _GetClient)
    monkeypatch.setattr(query_module, "print_result", lambda _result: None)
    return calls


def test_query_raw_paginate_preserves_backend_default_offset_mode(monkeypatch) -> None:
    import gulp_cli.commands.query as query

    calls = _install_query_client(monkeypatch, query)
    result = CliRunner().invoke(
        query.app,
        ["raw-paginate", "op-1", "--q", '{"query":{"match_all":{}}}'],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            "paginate",
            {
                "operation_id": "op-1",
                "q": {"query": {"match_all": {}}},
                "q_options": {"limit": 10, "offset": 0},
                "pagination_mode": None,
                "pit_id": None,
                "search_after": None,
            },
        )
    ]


def test_query_raw_paginate_preserves_mode_from_q_options(monkeypatch) -> None:
    import gulp_cli.commands.query as query

    calls = _install_query_client(monkeypatch, query)
    result = CliRunner().invoke(
        query.app,
        [
            "raw-paginate",
            "op-1",
            "--q",
            '{"query":{"match_all":{}}}',
            "--q-options",
            '{"pagination_mode":"pit","pit_id":"pit-current","search_after":[42,"cursor"]}',
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0][1]["q_options"] == {
        "limit": 10,
        "offset": 0,
        "pagination_mode": "pit",
        "pit_id": "pit-current",
        "search_after": [42, "cursor"],
    }
    assert calls[0][1]["pagination_mode"] is None


def test_query_raw_paginate_accepts_pit_cursor(monkeypatch) -> None:
    import gulp_cli.commands.query as query

    calls = _install_query_client(monkeypatch, query)
    result = CliRunner().invoke(
        query.app,
        [
            "raw-paginate",
            "op-1",
            "--q",
            '{"query":{"match_all":{}}}',
            "--limit",
            "50",
            "--offset",
            "100000",
            "--pagination-mode",
            "pit",
            "--pit-id",
            "pit-current",
            "--search-after",
            '[1725000000000,"shard-42"]',
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0][0] == "paginate"
    assert calls[0][1]["q_options"] == {"limit": 50, "offset": 100_000}
    assert calls[0][1]["pagination_mode"] == "pit"
    assert calls[0][1]["pit_id"] == "pit-current"
    assert calls[0][1]["search_after"] == [1_725_000_000_000, "shard-42"]


def test_query_raw_paginate_rejects_non_array_cursor(monkeypatch) -> None:
    import gulp_cli.commands.query as query

    _install_query_client(monkeypatch, query)
    result = CliRunner().invoke(
        query.app,
        [
            "raw-paginate",
            "op-1",
            "--q",
            '{"query":{"match_all":{}}}',
            "--search-after",
            '{"not":"an-array"}',
        ],
    )

    assert result.exit_code != 0
    assert "--search-after must be a JSON array" in result.output


def test_query_raw_paginate_close(monkeypatch) -> None:
    import gulp_cli.commands.query as query

    calls = _install_query_client(monkeypatch, query)
    result = CliRunner().invoke(
        query.app,
        ["raw-paginate-close", "op-1", "--pit-id", "pit-to-close"],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            "close",
            {"operation_id": "op-1", "pit_id": "pit-to-close"},
        )
    ]
