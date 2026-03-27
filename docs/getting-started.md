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

Delete and recreate operation before ingest (optional, destructive):

```bash
gulp-cli ingest file my_investigation win_evtx /gulp/samples/win_evtx/System.evtx --reset-operation
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

### Preview Before Ingest

```bash
gulp-cli ingest file my_investigation win_evtx /gulp/samples/win_evtx/System.evtx --preview
```

This runs parser preview without persisting documents.

### Wait for Completion

```bash
gulp-cli ingest file my_investigation win_evtx '/gulp/samples/win_evtx/*.evtx' --wait
```

This shows a real-time progress bar while documents are being ingested.

### Rebase Timestamps

If you need to shift document timestamps after ingestion:

```bash
gulp-cli db rebase-by-query my_investigation --offset-msec 3600000 --wait
```

This rebases `@timestamp` and `gulp.timestamp` forward by one hour.

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
gulp-cli query raw my_investigation --q '{"query":{"match_all":{}}}' --limit 10 --offset 0

# Synchronous preview mode
gulp-cli query raw my_investigation --q '{"query":{"match_all":{}}}' --preview
```

### Query with Filter

```bash
# Get only events from Security source
gulp-cli query gulp my_investigation --flt '{"source_ids":["security"]}'
```

### Aggregation Query

Compute a synchronous aggregation directly:

```bash
gulp-cli query aggregation my_investigation \
  --q '{"size":0,"aggs":{"by_event_code":{"terms":{"field":"event.code"}}}}'
```

### Get One Document by ID

```bash
gulp-cli query document-get-by-id my_investigation AVY84pUBM0e5DCHhCzDq
```

### Export Query Results to JSON

```bash
gulp-cli query gulp-export my_investigation \
  --flt '{"source_ids":["security"]}' \
  --output ./my_investigation-security.json
```

### Query External Source

```bash
gulp-cli query external my_investigation \
  --plugin query_elasticsearch \
  --plugin-params '{"custom_parameters":{"index":"external_logs"}}' \
  --q '{"query":{"match_all":{}}}' \
  --preview --limit 50 --offset 0
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

### Create a Note

At least one of `--time-pin` or `--doc` is required when creating a note.

```bash
gulp-cli collab note create my_investigation sdk_context security \
  "First analyst note" \
  "Review the process tree around the alert" \
  --time-pin 1774626000000000000
```

### List Notes

```bash
gulp-cli collab note list my_investigation
```

### Create a Link

```bash
gulp-cli collab link create my_investigation doc-a --doc-ids doc-b,doc-c \
  --name "same activity cluster"
```

### Create a Highlight

```bash
gulp-cli collab highlight create my_investigation \
  --time-range 1774626000000000000,1774626060000000000 \
  --name "Alert window"
```

### Delete a Note

```bash
gulp-cli collab note delete abc123def456
```

### Bulk Delete Collaboration Objects

```bash
# Delete notes matching a collab filter
gulp-cli collab note delete-bulk my_investigation \
  --flt '{"source_ids":["security"],"tags":["reviewed"]}'
```

### Bulk Delete Request Stats

```bash
gulp-cli stats delete-bulk my_investigation --flt '{"user_ids":["admin"]}'
```

### Cancel a Running Request

```bash
# Cancel by request id
gulp-cli stats cancel 903546ff-c01e-4875-a585-d7fa34a0d237

# Cancel and remove stats immediately
gulp-cli stats cancel 903546ff-c01e-4875-a585-d7fa34a0d237 --expire-now
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
gulp-cli collab --help

# Specific command help
gulp-cli ingest file --help
gulp-cli query raw --help
gulp-cli collab note create --help
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

## Step 10: User Groups and Access Control

Organize users into groups and control who can access which objects.

### Create groups and add users

```bash
# Create a read/edit analysts group
gulp-cli user-group create analysts --permission read,edit

# Add users
gulp-cli user-group add-user analysts alice
gulp-cli user-group add-user analysts bob

# List groups
gulp-cli user-group list
```

### Grant operation access to a group

```bash
# Operations require explicit grants — give the analysts group access
gulp-cli acl add-group incident-001 --obj-type operation --group-id analysts

# Grant a single user access to a note
gulp-cli acl add-user note-xyz --obj-type note --user-id alice

# Make a sensitive note visible only to its owner/admin
gulp-cli acl make-private note-xyz --obj-type note
```

---

## Step 11: Index Management

```bash
# List all OpenSearch indexes
gulp-cli db list-indexes

# Force a refresh so new documents are searchable immediately
gulp-cli db refresh-index incident-001

# Permanently delete an index and its data (with confirmation)
gulp-cli db delete-index old-test-op --yes
```

---

## Step 12: Storage Files

Use storage commands to inspect, download, and clean filestore objects.

```bash
# List files for an operation
gulp-cli storage list-files --operation-id my_investigation

# Download one file by storage id
gulp-cli storage get-file my_investigation \
  my_investigation/context-a/source-security/System.evtx \
  --output ./System.evtx

# Delete one file
gulp-cli storage delete-by-id my_investigation \
  my_investigation/context-a/source-security/System.evtx

# Delete all files for one operation
gulp-cli storage delete-by-tags --operation-id my_investigation
```

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
