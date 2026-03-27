# 🚀 gulp-cli

> THIS IS STILL WIP!

**A modern, powerful command-line interface for gULP** — manage forensic document ingestion, querying, enrichment, and collaboration entirely from your terminal.

## ✨ What can you do?

- 🔐 **Authentication** — secure login with token persistence
- 📥 **Ingestion** — ingest files (single/batch/wildcard), zip archives, with concurrent uploads
- 🔍 **Querying** — raw OpenSearch queries, Sigma rules, external plugins
- 🏷️ **Enrichment** — enrich documents, tag/untag, update fields
- 👥 **User Management** — create users, manage permissions (admin only)
- 📋 **Operations** — create/list/manage operations and contexts
- 🔌 **Plugins** — list/upload/download plugins and mapping files
- 📊 **Stats** — monitor ingestion and query requests
- 🎯 **Collaboration** — manage notes, links, highlights

All with **beautiful terminal output**, **automatic tab completion**, and **async-first design**.

---

## 🚀 Quick Start

### Installation

```bash
# Temporary setup: gulp-sdk is currently installed from GitHub via gulp-cli dependencies.
# In the future, both gulp-sdk and gulp-cli will be installable directly from PyPI.
# for now, clone this repository and install in development mode.
# you can use your existing gulp .venv or create a new one ...
python3 -m venv ./.venv
source ./.venv/bin/activate
git clone https://github.com/mentat-is/gulp-cli
cd gulp-cli && pip install -e .

# Verify installation
gulp-cli --help
```

### Basic Usage

```bash
# Login to your gULP instance
gulp-cli auth login --url http://localhost:8080 --username admin --password admin

# Check who you are
gulp-cli auth whoami

# List operations
gulp-cli operation list

# Ingest files with wildcard
gulp-cli ingest file my_operation win_evtx 'samples/win_evtx/*.evtx'

# Query documents
gulp-cli query raw my_operation --q '{"query":{"match_all":{}}}'
```
---

## 📚 Documentation

- **[Getting Started Guide](./docs/getting-started.md)** — auth, first operation, first ingest
- **[Command Reference](./docs/command-reference.md)** — all available commands and options
- **[Practical Examples](./docs/examples.md)** — real-world workflows and recipes
- **[Troubleshooting](./docs/troubleshooting-cli.md)** — common issues and solutions

---
