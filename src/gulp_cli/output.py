from __future__ import annotations

from typing import Any, Callable

from rich.console import Console
from rich.json import JSON
from rich.table import Table

console = Console()


def print_json(data: Any) -> None:
    console.print(JSON.from_data(data))


def print_error(message: str) -> None:
    console.print(f"[red]Error: {message}[/red]")


def print_warning(message: str) -> None:
    console.print(f"[yellow]Warning: {message}[/yellow]")


def print_kv_table(rows: list[tuple[str, Any]], title: str | None = None) -> None:
    table = Table(title=title)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")
    for key, value in rows:
        table.add_row(str(key), str(value))
    console.print(table)


def print_records(records: list[dict[str, Any]], title: str | None = None) -> None:
    if not records:
        console.print("[yellow]No results[/yellow]")
        return

    keys: list[str] = []
    for record in records:
        for key in record.keys():
            if key not in keys:
                keys.append(key)

    table = Table(title=title)
    for key in keys:
        table.add_column(str(key), overflow="fold")

    for record in records:
        table.add_row(*[str(record.get(key, "")) for key in keys])

    console.print(table)


def print_result(
    data: Any,
    verbose: bool = False,
    formatter: Callable[[Any], None] | None = None,
) -> None:
    """
    Print result data with conditional verbose mode.
    
    Args:
        data: The result data to print
        verbose: If True, always print full JSON output
        formatter: Callable that formats/prints the summary (called only if verbose=False)
    """
    if verbose:
        print_json(data)
    elif formatter:
        formatter(data)
    else:
        # Default: print full JSON if no formatter provided
        print_json(data)
