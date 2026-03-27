from __future__ import annotations

import asyncio

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_json
from gulp_cli.utils import parse_json_list_option, parse_json_option

app = typer.Typer(help="Query commands")


@app.command("raw")
def query_raw(
    operation_id: str,
    q: str = typer.Option(..., "--q", help="JSON object or array with OpenSearch DSL query/query list"),
    q_options: str | None = typer.Option(None, "--q-options", help="JSON object for GulpQueryParameters"),
    wait: bool = typer.Option(False, "--wait"),
) -> None:
    async def _run() -> None:
        q_parsed = parse_json_list_option(q, field_name="q")
        if not q_parsed:
            raise typer.BadParameter("--q is required")
        options = parse_json_option(q_options, field_name="q-options")
        async with get_client() as client:
            result = await client.queries.query_raw(
                operation_id=operation_id,
                q=q_parsed,
                q_options=options,
                wait=wait,
            )
            print_json(result)

    asyncio.run(_run())


@app.command("gulp")
def query_gulp(
    operation_id: str,
    flt: str | None = typer.Option(None, "--flt", help="JSON object for GulpQueryFilter"),
    q_options: str | None = typer.Option(None, "--q-options", help="JSON object for GulpQueryParameters"),
    wait: bool = typer.Option(False, "--wait"),
) -> None:
    async def _run() -> None:
        flt_parsed = parse_json_option(flt, field_name="flt")
        options = parse_json_option(q_options, field_name="q-options")
        async with get_client() as client:
            result = await client.queries.query_gulp(
                operation_id=operation_id,
                flt=flt_parsed,
                q_options=options,
                wait=wait,
            )
            print_json(result)

    asyncio.run(_run())
