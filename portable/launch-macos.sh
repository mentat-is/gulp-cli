#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export GULP_CLI_HOME="$SCRIPT_DIR/data"
mkdir -p "$GULP_CLI_HOME/extension"

exec "$SCRIPT_DIR/gulp-cli" "$@"