from __future__ import annotations

import asyncio

import typer

from gulp_cli.client import get_client
from gulp_cli.output import print_json, print_records, print_warning, print_result

app = typer.Typer(help="Storage (S3-compatible filestore) commands")


@app.command("list-files")
def list_files(
    operation_id: str | None = typer.Option(None, "--operation-id", help="Filter by operation ID"),
    context_id: str | None = typer.Option(None, "--context-id", help="Filter by context ID"),
    continuation_token: str | None = typer.Option(None, "--continuation-token", help="Pagination continuation token"),
    max_results: int = typer.Option(100, "--max-results", min=1, max=1000, help="Maximum results per page"),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """List files from the storage backend."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.storage.list_files(
                operation_id=operation_id,
                context_id=context_id,
                continuation_token=continuation_token,
                max_results=max_results,
            )

            files = result.get("files") if isinstance(result, dict) else None
            if as_json or not isinstance(files, list):
                print_result(result, verbose=verbose)
            else:
                print_result(files, verbose=verbose, formatter=lambda d: print_records(d, title="Storage Files"))
                token = result.get("continuation_token")
                if token:
                    print_warning(
                        "More results available. Re-run with --continuation-token "
                        + str(token)
                    )

    asyncio.run(_run())


@app.command("get-file")
def get_file(
    operation_id: str,
    storage_id: str,
    output_path: str = typer.Option(..., "--output", help="Local output file path"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Download a storage file by storage ID."""

    async def _run() -> None:
        async with get_client() as client:
            path = await client.storage.get_file_by_id(
                operation_id=operation_id,
                storage_id=storage_id,
                output_path=output_path,
            )
            print_result({"output_path": path}, verbose=verbose)

    asyncio.run(_run())


@app.command("delete-by-id")
def delete_by_id(
    operation_id: str,
    storage_id: str,
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Delete a storage file by storage ID."""

    async def _run() -> None:
        async with get_client() as client:
            result = await client.storage.delete_by_id(
                operation_id=operation_id,
                storage_id=storage_id,
            )
            print_result(result, verbose=verbose)

    asyncio.run(_run())


@app.command("delete-by-tags")
def delete_by_tags(
    operation_id: str | None = typer.Option(None, "--operation-id", help="Filter by operation ID"),
    context_id: str | None = typer.Option(None, "--context-id", help="Filter by context ID"),
    delete_all: bool = typer.Option(False, "--all", help="Delete files globally without any operation/context filter"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt when using --all"),
    verbose: bool = typer.Option(False, "--verbose", help="Print complete result JSON instead of summary"),
) -> None:
    """Delete storage files by operation/context tags."""

    async def _run() -> None:
        if not delete_all and not operation_id and not context_id:
            raise typer.BadParameter(
                "Provide --operation-id and/or --context-id, or pass --all for global delete"
            )
        if delete_all and not yes:
            typer.confirm(
                "This will delete storage files across all operations. Continue?",
                abort=True,
            )

        async with get_client() as client:
            result = await client.storage.delete_by_tags(
                operation_id=operation_id,
                context_id=context_id,
            )
            print_result(result, verbose=verbose)

    asyncio.run(_run())
