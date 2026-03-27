from __future__ import annotations

import typer

from gulp_cli.commands.acl import app as acl_app
from gulp_cli.commands.auth import app as auth_app
from gulp_cli.commands.collab import app as collab_app
from gulp_cli.commands.db import app as db_app
from gulp_cli.commands.ingest import app as ingest_app
from gulp_cli.commands.operations import app as operation_app
from gulp_cli.commands.query import app as query_app
from gulp_cli.commands.stats import app as stats_app
from gulp_cli.commands.storage import app as storage_app
from gulp_cli.commands.user_group import app as user_group_app
from gulp_cli.commands.users import app as user_app

app = typer.Typer(
    no_args_is_help=True,
    help="Modern CLI for gULP, powered by gulp-sdk",
)

app.add_typer(auth_app, name="auth")
app.add_typer(user_app, name="user")
app.add_typer(user_group_app, name="user-group")
app.add_typer(operation_app, name="operation")
app.add_typer(ingest_app, name="ingest")
app.add_typer(query_app, name="query")
app.add_typer(stats_app, name="stats")
app.add_typer(storage_app, name="storage")
app.add_typer(collab_app, name="collab")
app.add_typer(db_app, name="db")
app.add_typer(acl_app, name="acl")
