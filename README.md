# 🚀 gulp-cli

**A modern, powerful command-line interface for gULP** — manage forensic document ingestion, querying, enrichment, and collaboration entirely from your terminal.

## ✨ What can you do?

- 🔐 **Authentication** — secure login with token persistence
- 📥 **Ingestion** — ingest files (single/batch/wildcard), zip archives, with concurrent uploads
- 🔍 **Querying** — raw OpenSearch queries, Sigma rules, external plugins
- 🏷️ **Enrichment** — enrich documents, tag/untag, update fields
- 👥 **User Management** — create users, manage permissions (admin only)
- 📋 **Operations** — create/list/manage operations and contexts
- 🔌 **Plugins** — list/upload/download plugins and mapping files
- 🗺️ **Enhance Maps** — map document fields (e.g., `gulp.event_code`) to glyph/color per plugin
- 🖼️ **Glyphs** — create/list/update/delete custom glyphs
- 🧩 **Dynamic Extensions** — load custom CLI commands from internal or user extension folders
- 📊 **Stats** — monitor ingestion and query requests
- 🎯 **Collaboration** — manage notes, links, highlights

All with **beautiful terminal output**, **automatic tab completion**, and **async-first design**.

---

## 🚀 Quick Start

### Installation

```bash
# from pip
pip install gulp-cli

# or, for the latest development version:
python3 -m venv ./.venv
source ./.venv/bin/activate
git clone https://github.com/mentat-is/gulp-cli
cd gulp-cli && pip install -e .

# Verify installation
gulp-cli --help
```

### Basic Usage

> for the cli to work, set `"ws_ignore_missing": true` (should be default in the v1.6.51 backend, though ...) in your `gulp_cfg.json` to prevent the backend from halting operations when the CLI disconnects its websocket after sending an async request!
 
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
- **[Extensions Guide](./docs/extensions.md)** — dynamic extension loading and custom command contract
- **[Resource Management Commands](./docs/resource-management.md)** — context, source, plugin, mapping, enhance-map, glyph
- **[Practical Examples](./docs/examples.md)** — real-world workflows and recipes
- **[Troubleshooting](./docs/troubleshooting-cli.md)** — common issues and solutions

---
