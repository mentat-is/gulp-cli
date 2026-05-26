@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "GULP_CLI_HOME=%SCRIPT_DIR%data"

if not exist "%GULP_CLI_HOME%\extension" mkdir "%GULP_CLI_HOME%\extension"

"%SCRIPT_DIR%gulp-cli.exe" %*