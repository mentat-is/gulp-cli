from __future__ import annotations

import typer

from gulp_cli.commands.auth import app as auth_app
from gulp_cli.commands.ingest import app as ingest_app
from gulp_cli.commands.operations import app as operation_app
from gulp_cli.commands.query import app as query_app
from gulp_cli.commands.users import app as user_app

app = typer.Typer(
    no_args_is_help=True,
    help="Modern CLI for gULP, powered by gulp-sdk",
)

app.add_typer(auth_app, name="auth")
app.add_typer(user_app, name="user")
app.add_typer(operation_app, name="operation")
app.add_typer(ingest_app, name="ingest")
app.add_typer(query_app, name="query")
