# Getting Started with gulp-cli

Complete beginner's guide to using gulp-cli for the first time.

---

## Step 1: Installation

```bash
# Install the CLI
pip install -e /gulp/gulp-cli

# Verify it works
gulp-cli --help
```

See [Installation Guide](installation.md) for detailed setup.

---

## Step 2: Start a gULP Instance

If you don't have a gULP server running, start one:

```bash
# In one terminal, start gULP with a test operation
gulp --reset-collab --create test_operation

# This creates a clean instance with:
# - A test operation named "test_operation"
# - Default users: admin/admin, guest/guest
```

Keep this terminal open. In another terminal, proceed with authentication.

---

## Step 3: Authenticate

### Login

```bash
gulp-cli auth login --url http://localhost:8080 --username admin --password admin
```

This:
- Connects to your gULP instance
- Exchanges credentials for a token
- Stores token in `~/.config/gulp-cli/config.json`

**Output should be:**
```
✓ Authentication successful
Token stored in ~/.config/gulp-cli/config.json
```

### Verify Authentication

```bash
gulp-cli auth whoami
```

**Expected output:**
```
├─ User: admin
├─ Permissions: admin
└─ URL: http://localhost:8080
```

### Switch Users

You can login as different users:

```bash
gulp-cli auth login --url http://localhost:8080 --username guest --password guest
gulp-cli auth whoami  # Should show "guest" with read-only permissions
```

### Logout

Clear your token:

```bash
gulp-cli auth logout
# Now you're logged out and must re-authenticate
```

---

## Step 4: Your First Operation

Let's explore operations.

### List Existing Operations

```bash
gulp-cli operation list
```

**Expected output:**
```
╭────────────────────────────────────────────────────╮
│                   OPERATIONS                       │
├─────────────────────┬──────────────────────────────┤
│ ID                  │ test_operation               │
│ Display Name        │ test_operation               │
│ Owner               │ admin                        │
│ Created             │ 2026-03-27T10:30:00          │
│ Document Count      │ 0                            │
└─────────────────────┴──────────────────────────────┘
```

### Create a New Operation

```bash
gulp-cli operation create my_investigation --description "Investigation into incident #123"
```

**Expected output:**
```
✓ Operation created successfully
ID: my_investigation
```

### Get Operation Details

```bash
gulp-cli operation get my_investigation
```

---

## Step 5: Your First Ingestion

Now let's ingest some documents.

### Prepare Test Data

The gULP repository includes sample Windows Event logs:

```bash
ls -la /gulp/samples/win_evtx/
# Shows: System.evtx, Security.evtx, Application.evtx, ...
```

### Ingest Files

Ingest a single file:

```bash
gulp-cli ingest file my_investigation win_evtx /gulp/samples/win_evtx/System.evtx
```

**Expected output:**
```
📥 Ingesting files...
✓ /gulp/samples/win_evtx/System.evtx
Documents queued for processing
```

### Ingest Multiple Files with Wildcard

```bash
gulp-cli ingest file my_investigation win_evtx '/gulp/samples/win_evtx/*.evtx'
```

This ingests all `.evtx` files concurrently.

### Wait for Completion

```bash
gulp-cli ingest file my_investigation win_evtx '/gulp/samples/win_evtx/*.evtx' --wait
```

This shows a real-time progress bar while documents are being ingested.

---

## Step 6: Your First Query

Once documents are ingested, you can query them.

### Simple Query (Match All)

```bash
gulp-cli query raw my_investigation --q '{"query":{"match_all":{}}}'
```

**Expected output:**
```
╭────────────────────────────────────────────────────────╮
│                    QUERY RESULTS                       │
├────────────────────────────────────────────────────────┤
│ Total Hits: 5231                                       │
│ Query Time: 145ms                                      │
│ Source: System.evtx (4200 docs)                        │
│         Security.evtx (1031 docs)                      │
└────────────────────────────────────────────────────────┘
```

### Query with Limit

```bash
gulp-cli query raw my_investigation --q '{"query":{"match_all":{}}}' --limit 10
```

### Query with Filter

```bash
# Get only events from Security source
gulp-cli query gulp my_investigation --flt '{"source":"Security"}'
```

### Sigma Rule Query

Assuming you have a Sigma rule file:

```bash
gulp-cli query sigma my_investigation --rule-file /path/to/process_creation.yml
```

---

## Step 7: Tagging & Enrichment

### Tag Documents

Tag all documents from a specific source:

```bash
gulp-cli enrich tag my_investigation \
  --flt '{"source":"Security"}' \
  --tag "security-log" \
  --tag "reviewed"
```

### Untag Documents

```bash
gulp-cli enrich untag my_investigation \
  --flt '{"tag":"reviewed"}' \
  --tag "reviewed"
```

### Update Document Fields

Set a custom field on matching documents:

```bash
gulp-cli enrich update my_investigation \
  --flt '{"event_id":4688}' \
  --fields '{"threat_level":"high"}'
```

---

## Step 8: Collaboration Notes

Add and view collaboration objects (notes, links, highlights).

### List Notes

```bash
gulp-cli collab note list my_investigation --limit 20
```

### Delete a Note

```bash
gulp-cli collab note delete my_investigation --note-id abc123def456
```

---

## Step 9: Explore Help

Every command has detailed help:

```bash
# General help
gulp-cli --help

# Command group help
gulp-cli ingest --help
gulp-cli query --help
gulp-cli enrich --help

# Specific command help
gulp-cli ingest file --help
gulp-cli query raw --help
```

---

## Common Workflows

### Full Forensic Investigation Workflow

```bash
# 1. Create operation
gulp-cli operation create incident-2026-001

# 2. Ingest all evidence
gulp-cli ingest file incident-2026-001 win_evtx '/evidence/windows/*.evtx' --wait

# 3. Run initial queries
gulp-cli query raw incident-2026-001 --q '{"query":{"match_all":{}}}'

# 4. Apply Sigma rules
gulp-cli query sigma incident-2026-001 --rule-file /rules/process_creation.yml

# 5. Tag suspicious results
gulp-cli enrich tag incident-2026-001 \
  --flt '{"event_id":"4688","parent_process":"powershell.exe"}' \
  --tag "suspicious" --tag "requires-review"

# 6. Export findings
gulp-cli query gulp incident-2026-001 \
  --flt '{"tag":"suspicious"}' \
  --output-format json > findings.json
```

### Multi-Source Investigation

```bash
# Create operation
gulp-cli operation create multi-source-incident

# Ingest from different sources
gulp-cli ingest file multi-source-incident win_evtx '/data/windows/*.evtx'
gulp-cli ingest file multi-source-incident syslog '/data/linux/**/*.log'
gulp-cli ingest file multi-source-incident pcap '/data/network/*.pcap'

# Query across all sources
gulp-cli query raw multi-source-incident --q '{"query":{"match_all":{}}}'

# Filter by source
gulp-cli query gulp multi-source-incident --flt '{"source":"windows"}'
```

---

## Next Steps

1. **[Command Reference](command-reference.md)** — detailed documentation for all commands
2. **[Practical Examples](examples.md)** — advanced use cases and recipes
3. **[Troubleshooting](troubleshooting-cli.md)** — common issues and solutions

---

## Tips & Tricks

### Use Aliases

Speed up your workflow with shell aliases:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias gc='gulp-cli'
alias gop='gulp-cli operation'
alias gq='gulp-cli query'

# Now use:
gop list
gq raw my_operation --q '{"query":{"match_all":{}}}'
```

### Tab Completion

Enable shell tab completion:

```bash
# For bash
eval "$(_GULP_CLI_COMPLETE=bash_source gulp-cli)"

# For zsh
eval "$(_GULP_CLI_COMPLETE=zsh_source gulp-cli)"

# Add to your ~/.bashrc or ~/.zshrc for persistence
```

### Output Formats

Control output format globally:

```bash
# JSON output (good for scripting)
export GULP_OUTPUT_FORMAT=json
gulp-cli operation list

# Table output (default, pretty)
export GULP_OUTPUT_FORMAT=table

# Text output (minimal)
export GULP_OUTPUT_FORMAT=text
```

### External Plugin Queries

Query with external plugins:

```bash
gulp-cli query external my_operation \
  --plugin query_elasticsearch \
  --plugin-params '{"index":"my_index","query":"admin"}'
```

---

## Getting Help

- **Check help flags:** `gulp-cli --help`, `gulp-cli <command> --help`
- **See troubleshooting:** [Troubleshooting Guide](troubleshooting-cli.md)
- **Check examples:** [Practical Examples](examples.md)

Happy investigating! 🔎
