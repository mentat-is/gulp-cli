# gulp-cli Installation & Setup

## Prerequisites

- **Python 3.12+** (tested on 3.12, 3.13)
- **pip**
- **gULP instance** running (local or remote)
- **gulp-sdk** (automatically installed as dependency)

## Installation Methods

### 1. Development Mode (Recommended for now)

Install directly from the local repository:

```bash
cd /gulp
pip install -e ./gulp-cli
```

This:
- Links the CLI to your Python environment
- Updates automatically when you modify source code
- Makes `gulp-cli` command available globally

Verify installation:
```bash
gulp-cli --version
gulp-cli --help
```

### 2. Editable Install in a Virtual Environment

Best practice for isolated development:

```bash
# Create and activate venv
python3 -m venv ~/.venvs/gulp-cli
source ~/.venvs/gulp-cli/bin/activate

# Install
pip install -e /gulp/gulp-cli

# Verify
gulp-cli --help
```

### 3. Production Install (when packaged)

```bash
pip install gulp-cli
```

---

## System-Specific Setup

### macOS

```bash
# Using Homebrew Python
brew install python@3.12
python3.12 -m venv ~/.venvs/gulp-cli
source ~/.venvs/gulp-cli/bin/activate

# Install CLI
pip install -e /gulp/gulp-cli
```

### Linux (Ubuntu/Debian)

```bash
# Install Python dev tools
sudo apt update
sudo apt install python3.9-dev python3-pip python3-venv

# Create venv
python3 -m venv ~/.venvs/gulp-cli
source ~/.venvs/gulp-cli/bin/activate

# Install CLI
pip install -e /gulp/gulp-cli
```

### Windows (WSL2)

```bash
# Inside WSL2 Ubuntu terminal
python3 -m venv ~/.venvs/gulp-cli
source ~/.venvs/gulp-cli/bin/activate

pip install -e /gulp/gulp-cli
```

---

## Verify Installation

```bash
# Show version
gulp-cli --version

# Show all available commands
gulp-cli --help

# Test connection (no auth required)
gulp-cli auth whoami  # Should fail if not logged in (expected)
```

---

## Configuration

### Config Directory

The CLI stores configuration in:
```
~/.config/gulp-cli/
```

This includes:
- `config.json` — server URL and authentication token

**Custom location:**
```bash
export GULP_CONFIG_DIR=~/.my-gulp-config
gulp-cli auth login  # Uses custom directory
```

### Environment Variables

Override defaults with environment variables:

```bash
# Override server URL
export GULP_URL=http://prod.example.com:8080

# Override authentication token
export GULP_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGc...

# Override config directory
export GULP_CONFIG_DIR=/etc/gulp-cli

# Set output format
export GULP_OUTPUT_FORMAT=json

# Use in commands
GULP_URL=http://backup.local:8080 gulp-cli operation list
```

---

## Next Steps

1. **[Getting Started Guide](getting-started.md)** — first login and basic operations
2. **[Command Reference](command-reference.md)** — all available commands
3. **[Practical Examples](examples.md)** — real-world use cases

---

## Troubleshooting Installation

### `command not found: gulp-cli`

Ensure it's installed and your PATH includes the environment:
```bash
# Reinstall
pip install -e /gulp/gulp-cli

# Check where it's installed
which gulp-cli

# If using venv, ensure it's activated
source ~/.venvs/gulp-cli/bin/activate
```

### `ImportError: No module named 'gulp_sdk'`

The `gulp-sdk` dependency wasn't installed. Reinstall:
```bash
pip install -e /gulp/gulp-cli
```

### Permission Denied

On Unix-like systems, ensure the script is executable:
```bash
chmod +x $(which gulp-cli)
```

### Python Version Mismatch

Verify Python version:
```bash
python3 --version  # Should be 3.9+

# Or use explicit version
python3.12 -m pip install -e /gulp/gulp-cli
```

---

## Uninstall

```bash
pip uninstall gulp-cli
```

To completely remove configuration:
```bash
rm -rf ~/.config/gulp-cli
```

---

## Getting Help

```bash
# General help
gulp-cli --help

# Command-specific help
gulp-cli auth --help
gulp-cli ingest file --help
gulp-cli query raw --help
```
