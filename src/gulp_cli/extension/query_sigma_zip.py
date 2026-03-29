from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer

from gulp_cli.output import print_result
from gulp_cli.utils import comma_split, parse_json_option


def _parse_csv_option(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return comma_split(raw)


def register_extension(
    *,
    command_groups: dict[str, typer.Typer],
    get_client: Any,
    **_: Any,
) -> None:
    """
    Register query command for the query_sigma_zip extension endpoint.
    """
    query_app = command_groups.get("query")
    if query_app is None:
        raise RuntimeError("Query command group not available")

    @query_app.command("sigma-zip", rich_help_panel="Extension Commands")
    def query_sigma_zip(
        operation_id: str,
        zip_file: str = typer.Option(
            ...,
            "--zip-file",
            help="Path to ZIP archive containing Sigma YAML rules",
        ),
        src_ids: str | None = typer.Option(
            None,
            "--src-ids",
            help="Comma-separated source IDs",
        ),
        levels: str | None = typer.Option(
            None,
            "--levels",
            help="Comma-separated sigma levels (default server-side: high,critical)",
        ),
        tags: str | None = typer.Option(
            None,
            "--tags",
            help="Comma-separated sigma tags",
        ),
        products: str | None = typer.Option(
            None,
            "--products",
            help="Comma-separated sigma logsource products",
        ),
        categories: str | None = typer.Option(
            None,
            "--categories",
            help="Comma-separated sigma logsource categories",
        ),
        services: str | None = typer.Option(
            None,
            "--services",
            help="Comma-separated sigma logsource services",
        ),
        q_options: str | None = typer.Option(
            None,
            "--q-options",
            help="JSON object for GulpQueryParameters",
        ),
        wait: bool = typer.Option(False, "--wait", help="Wait for completion"),
        timeout: int = typer.Option(
            120,
            "--timeout",
            min=0,
            help="Wait timeout in seconds (0 means no timeout)",
        ),
    ) -> None:
        """Extension: query documents using sigma rules from a ZIP archive."""

        async def _run() -> None:
            zip_path = Path(zip_file).expanduser()
            if not zip_path.exists() or not zip_path.is_file():
                raise typer.BadParameter(
                    f"Invalid --zip-file path: {zip_path}",
                    param_hint="--zip-file",
                )

            parsed_q_options = parse_json_option(q_options, field_name="q-options")

            async with get_client() as client:
                result = await client.queries.query_sigma_zip(
                    operation_id=operation_id,
                    zip_path=str(zip_path),
                    src_ids=_parse_csv_option(src_ids),
                    levels=_parse_csv_option(levels),
                    products=_parse_csv_option(products),
                    categories=_parse_csv_option(categories),
                    services=_parse_csv_option(services),
                    tags=_parse_csv_option(tags),
                    q_options=parsed_q_options,
                    wait=wait,
                    timeout=timeout,
                )
                print_result(result)

        asyncio.run(_run())
