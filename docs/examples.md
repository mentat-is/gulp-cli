- [gulp-cli Practical Examples](#gulp-cli-practical-examples)
  - [Quick Reference Examples](#quick-reference-examples)
    - [Authentication](#authentication)
  - [Ingestion Workflows](#ingestion-workflows)
    - [Single File Ingestion](#single-file-ingestion)
    - [Bulk File Ingestion with Wildcard](#bulk-file-ingestion-with-wildcard)
    - [Concurrent Multi-Source Ingestion](#concurrent-multi-source-ingestion)
    - [CSV Data Ingestion with Custom Parameters](#csv-data-ingestion-with-custom-parameters)
    - [JSON Logs Ingestion](#json-logs-ingestion)
    - [Add More Evidence to Existing Source](#add-more-evidence-to-existing-source)
  - [Request Stats Monitoring Workflows](#request-stats-monitoring-workflows)
    - [Monitor Ongoing Requests (Live)](#monitor-ongoing-requests-live)
    - [Get One Request Stat By Id](#get-one-request-stat-by-id)
    - [Inspect All Request Stats Once](#inspect-all-request-stats-once)
    - [Focus on Failed Requests](#focus-on-failed-requests)
    - [Filter by User, Type, and Server](#filter-by-user-type-and-server)
    - [Filter by Creation Time Window](#filter-by-creation-time-window)
    - [Use Stats While Ingestion Is Running](#use-stats-while-ingestion-is-running)
    - [Bulk Delete Request Stats](#bulk-delete-request-stats)
    - [Cancel a Running Request](#cancel-a-running-request)
  - [Rebase Workflows](#rebase-workflows)
    - [Shift All Documents Forward in Time](#shift-all-documents-forward-in-time)
    - [Rebase Only a Filtered Subset](#rebase-only-a-filtered-subset)
    - [Rebase with a Custom Script](#rebase-with-a-custom-script)
  - [Collaboration Workflows](#collaboration-workflows)
    - [Create a Time-Pinned Note](#create-a-time-pinned-note)
    - [Create a Note Attached to a Document](#create-a-note-attached-to-a-document)
    - [Update and List Notes](#update-and-list-notes)
    - [Create and Maintain Links Between Documents](#create-and-maintain-links-between-documents)
    - [Create and Update Highlights](#create-and-update-highlights)
    - [Export Raw Collaboration Objects as JSON](#export-raw-collaboration-objects-as-json)
    - [Bulk Delete Collaboration Objects](#bulk-delete-collaboration-objects)
  - [Query Workflows](#query-workflows)
    - [Match All Documents (Discovery)](#match-all-documents-discovery)
    - [Search by Field Value](#search-by-field-value)
    - [Complex Queries (Range, Boolean)](#complex-queries-range-boolean)
    - [Filter by Source](#filter-by-source)
    - [Aggregation, Document Lookup, and History](#aggregation-document-lookup-and-history)
  - [Sigma Rule Queries](#sigma-rule-queries)
    - [Run Single Sigma Rule](#run-single-sigma-rule)
    - [Run Rule with Severity Filtering](#run-rule-with-severity-filtering)
    - [Run Rule on Specific Source](#run-rule-on-specific-source)
    - [Multiple Sigma Rules in Batch](#multiple-sigma-rules-in-batch)
  - [Enrichment \& Tagging Workflows](#enrichment--tagging-workflows)
    - [Tag Suspicious Events](#tag-suspicious-events)
    - [Apply Threat Level Classification](#apply-threat-level-classification)
    - [Track Analysis Progress](#track-analysis-progress)
    - [Remove Enrichment Data](#remove-enrichment-data)
  - [User \& Operation Management](#user--operation-management)
    - [Create Multi-User Investigation Environment](#create-multi-user-investigation-environment)
    - [Archive Investigation (Revoke Access)](#archive-investigation-revoke-access)
    - [Inspect and Revoke User Sessions](#inspect-and-revoke-user-sessions)
  - [Advanced Workflows](#advanced-workflows)
    - [Full Forensic Investigation Pipeline](#full-forensic-investigation-pipeline)
    - [Batch Processing Multiple Operations](#batch-processing-multiple-operations)
    - [Integration with External Tools](#integration-with-external-tools)
  - [Tips \& Tricks](#tips--tricks)
    - [Use Aliases for Speed](#use-aliases-for-speed)
    - [Use Environment Variables for Repetitive Tasks](#use-environment-variables-for-repetitive-tasks)
    - [Parallel Processing with GNU Parallel](#parallel-processing-with-gnu-parallel)
    - [Monitor Long-Running Operations](#monitor-long-running-operations)
  - [Common Error Handling](#common-error-handling)
  - [User Group Workflows](#user-group-workflows)
    - [Set Up Role-Based Access](#set-up-role-based-access)
    - [Update and Clean Up Groups](#update-and-clean-up-groups)
  - [ACL / Access Control Workflows](#acl--access-control-workflows)
    - [Grant Operation Access to a Group](#grant-operation-access-to-a-group)
    - [Grant Access to Individual Users](#grant-access-to-individual-users)
    - [Private / Public Objects](#private--public-objects)
  - [Index Management Workflows](#index-management-workflows)
    - [Inspect Indexes](#inspect-indexes)
    - [Refresh After Ingestion](#refresh-after-ingestion)
    - [Remove a Stale Investigation (Destructive)](#remove-a-stale-investigation-destructive)
  - [Storage Workflows](#storage-workflows)
    - [List Stored Files](#list-stored-files)
    - [Download a File by Storage ID](#download-a-file-by-storage-id)
    - [Delete Files by ID or Tags](#delete-files-by-id-or-tags)
  - [Enhance Map and Glyph Workflows](#enhance-map-and-glyph-workflows)
    - [Create and Assign Custom Glyphs](#create-and-assign-custom-glyphs)
    - [Map Event Codes to Glyph/Color](#map-event-codes-to-glyphcolor)
    - [Change or Remove a Mapping](#change-or-remove-a-mapping)
  - [Extension Examples (story and sigma-zip)](#extension-examples-story-and-sigma-zip)
    - [Query Sigma Rules from ZIP (Extension)](#query-sigma-rules-from-zip-extension)
    - [Override Built-in Extension with User Extension](#override-built-in-extension-with-user-extension)
    - [Story Extension Workflows](#story-extension-workflows)
      - [Create an Incident Story](#create-an-incident-story)
      - [Update Story Content](#update-story-content)
      - [List and Inspect Stories](#list-and-inspect-stories)
  - [See Also](#see-also)

# gulp-cli Practical Examples

Real-world workflows and recipes for common investigation scenarios.

---

## Quick Reference Examples

### Authentication

```bash
# Login (first time setup)
gulp-cli auth login --url http://localhost:8080 --username admin --password admin

# Save a second session too
gulp-cli auth login --url http://localhost:8080 --username guest --password guest

# Check who you are
gulp-cli auth whoami

# Run a single command as another already-logged-in user
gulp-cli --as-user guest auth whoami

# Switch server
gulp-cli auth login --url http://prod.server.local:8080 --username analyst --password pass

# Logout one saved session
gulp-cli auth logout
```

---

## Ingestion Workflows

### Single File Ingestion

```bash
# Ingest one event log
gulp-cli ingest file incident-001 win_evtx /path/to/System.evtx

# Optional: delete and recreate operation before ingestion
gulp-cli ingest file incident-001 win_evtx /path/to/System.evtx --reset-operation
```

### Bulk File Ingestion with Wildcard

```bash
# Ingest all .evtx files from directory
gulp-cli ingest file incident-001 win_evtx '/evidence/**/*.evtx'

# Ingest from multiple locations
gulp-cli ingest file incident-001 win_evtx '/suspect-machine/*.evtx' '/network-share/backups/*.evtx'

# Preview parser output without ingesting
gulp-cli ingest file incident-001 win_evtx '/suspect-machine/System.evtx' --preview
```

### Concurrent Multi-Source Ingestion

```bash
# Create operation for multi-source investigation
gulp-cli operation create incident-2026-001

# Ingest evidence from different sources concurrently
gulp-cli ingest file incident-2026-001 win_evtx '/forensic/windows/*.evtx' --wait &
gulp-cli ingest file incident-2026-001 syslog '/forensic/linux/**/*.log' --wait &
gulp-cli ingest file incident-2026-001 pcap '/forensic/network/*.pcap' --wait &

wait  # Wait for all background jobs
```

### CSV Data Ingestion with Custom Parameters

```bash
# Ingest CSV with specific delimiter and encoding
gulp-cli ingest file incident-001 csv /data/access_log.csv \
  --plugin-params '{"delimiter":";","encoding":"iso-8859-1","has_header":true}'
```

### JSON Logs Ingestion

```bash
# Ingest JSON logs
gulp-cli ingest file incident-001 json '/logs/**/*.json' --wait
```

### Add More Evidence to Existing Source

```bash
# First ingestion creates data-2026-001 source
gulp-cli ingest file incident-001 win_evtx /initial/evidence.evtx

# Later, add more files to same source
gulp-cli ingest file-to-source incident-001 data-2026-001 win_evtx /additional/evidence.evtx --wait
```

---

## Request Stats Monitoring Workflows

### Monitor Ongoing Requests (Live)

```bash
# Default behavior: ongoing-only + live refresh
gulp-cli stats list incident-001
```

### Get One Request Stat By Id

```bash
gulp-cli stats get 903546ff-c01e-4875-a585-d7fa34a0d237
```

### Inspect All Request Stats Once

```bash
# Disable live refresh for a static snapshot
gulp-cli stats list incident-001 --all --no-live
```

### Focus on Failed Requests

```bash
# Show only request stats that contain errors
gulp-cli stats list incident-001 --all --errors present --no-live
```

### Filter by User, Type, and Server

```bash
# Only ingestion requests started by admin
gulp-cli stats list incident-001 --all --user-id admin --req-type ingest --no-live

# Only requests handled by a specific server instance
gulp-cli stats list incident-001 --all --server-id my-server-1 --no-live
```

### Filter by Creation Time Window

```bash
# ISO8601 window
gulp-cli stats list incident-001 --all \
  --time-created-from '2026-03-27T09:00:00Z' \
  --time-created-to '2026-03-27T18:00:00Z' \
  --no-live

# Epoch timestamp window
gulp-cli stats list incident-001 --all \
  --time-created-from 1774602000000 \
  --time-created-to 1774634400000 \
  --no-live
```

### Use Stats While Ingestion Is Running

```bash
# Terminal 1: start ingestion
gulp-cli ingest file incident-001 win_evtx '/evidence/**/*.evtx'

# Terminal 2: watch request stats with faster refresh
gulp-cli stats list incident-001 --refresh-seconds 0.5
```

### Bulk Delete Request Stats

```bash
# Delete request stats created by admin
gulp-cli stats delete-bulk incident-001 \
  --flt '{"user_ids":["admin"]}'

# Delete all request stats in the operation
gulp-cli stats delete-bulk incident-001 --all
```

### Cancel a Running Request

```bash
# Cancel with default grace window for stats cleanup
gulp-cli stats cancel 903546ff-c01e-4875-a585-d7fa34a0d237

# Cancel and purge stats immediately
gulp-cli stats cancel 903546ff-c01e-4875-a585-d7fa34a0d237 --expire-now
```

---

## Rebase Workflows

### Shift All Documents Forward in Time

```bash
gulp-cli db rebase-by-query incident-001 --offset-msec 3600000 --wait
```

### Rebase Only a Filtered Subset

```bash
gulp-cli db rebase-by-query incident-001 \
  --offset-msec -300000 \
  --flt '{"source_ids":["security"]}' \
  --wait
```

### Rebase with a Custom Script

```bash
gulp-cli db rebase-by-query incident-001 \
  --offset-msec 0 \
  --script 'ctx._source["custom_ts"] = params.now;'
```

---

## Collaboration Workflows

### Create a Time-Pinned Note

```bash
gulp-cli collab note create incident-001 sdk_context security \
  "Analyst note" \
  "Suspicious login spike around privilege escalation" \
  --time-pin 1774626000000000000 \
  --tags suspicious,review
```

### Create a Note Attached to a Document

```bash
gulp-cli collab note create incident-001 sdk_context security \
  "Document note" \
  "Inspect parent process and command line" \
  --doc '{"_id":"doc-123","gulp.operation_id":"incident-001","gulp.source_id":"security"}'
```

### Update and List Notes

```bash
gulp-cli collab note update note-123 --text "Reviewed by analyst-2" --tags reviewed,done
gulp-cli collab note list incident-001
```

### Create and Maintain Links Between Documents

```bash
# Correlate one source document to multiple targets
gulp-cli collab link create incident-001 doc-a --doc-ids doc-b,doc-c \
  --name "same user session" \
  --description "Events related by identical logon session id"

# Update the target set later
gulp-cli collab link update link-123 --doc-ids doc-b,doc-d

# Inspect links
gulp-cli collab link list incident-001
```

### Create and Update Highlights

```bash
# Mark a suspicious time window
gulp-cli collab highlight create incident-001 \
  --time-range 1774626000000000000,1774626060000000000 \
  --name "Burst of activity" \
  --color red \
  --tags suspicious,timeline

# Expand the reviewed window
gulp-cli collab highlight update hl-123 \
  --time-range 1774626000000000000,1774626120000000000

# Inspect highlights
gulp-cli collab highlight list incident-001
```

### Export Raw Collaboration Objects as JSON

Use `--verbose` to get full JSON output globally.

```bash
gulp-cli --verbose collab note list incident-001
gulp-cli --verbose collab link list incident-001
gulp-cli --verbose collab highlight list incident-001
```

### Bulk Delete Collaboration Objects

```bash
# Delete reviewed notes from a specific source
gulp-cli collab note delete-bulk incident-001 \
  --flt '{"source_ids":["security"],"tags":["reviewed"]}'

# Delete links that reference a specific document id
gulp-cli collab link delete-bulk incident-001 \
  --flt '{"doc_ids":["doc-a"]}'

# Delete highlights created in a specific time window
gulp-cli collab highlight delete-bulk incident-001 \
  --flt '{"time_created_range":[1774626000000,1774629600000]}'

# Delete every note in the operation
gulp-cli collab note delete-bulk incident-001 --all
```

---

## Query Workflows

### Match All Documents (Discovery)

```bash
# Get overview of ingested data
gulp-cli query raw incident-001 --q '{"query":{"match_all":{}}}'

# Fast synchronous preview
gulp-cli query raw incident-001 --q '{"query":{"match_all":{}}}' --preview
```

### Search by Field Value

```bash
# Find all login events
gulp-cli query raw incident-001 \
  --q '{"query":{"term":{"EventID":{"value":4624}}}}'

# Find events from specific computer
gulp-cli query raw incident-001 \
  --q '{"query":{"term":{"Computer":{"value":"SUSPECT-PC-001"}}}}'
```

### Complex Queries (Range, Boolean)

```bash
# Find security events from last 24 hours
gulp-cli query raw incident-001 \
  --q '{
    "query": {
      "bool": {
        "must": [
          {"term": {"EventID": 4688}},
          {"range": {"EventTime": {"gte": "now-24h"}}}
        ]
      }
    }
  }'

# Multiple OR conditions
gulp-cli query raw incident-001 \
  --q '{
    "query": {
      "bool": {
        "should": [
          {"term": {"EventID": 4625}},
          {"term": {"EventID": 4624}},
          {"term": {"EventID": 4688}}
        ],
        "minimum_should_match": 1
      }
    }
  }'
```

### Filter by Source

```bash
# Query only Security events
gulp-cli query gulp incident-001 --flt '{"source_ids":["security"]}'

# Query only events tagged as "suspicious"
gulp-cli query gulp incident-001 --flt '{"tags":["suspicious"]}'

# Preview filtered results
gulp-cli query gulp incident-001 --flt '{"tags":["suspicious"]}' --preview

# Paginated results via q_options overrides
gulp-cli query gulp incident-001 --flt '{"tags":["suspicious"]}' --limit 200 --offset 400

### Query External Data Source

```bash
gulp-cli query external incident-001 \
  --plugin query_elasticsearch \
  --plugin-params '{"custom_parameters":{"index":"external_logs"}}' \
  --q '{"query":{"match_all":{}}}' \
  --preview --limit 100 --offset 0
```
```

### Export Query Results

```bash
# Export Gulp query results to a JSON file
gulp-cli query gulp-export incident-001 \
  --flt '{"source_ids":["security"]}' \
  --output findings.json

# Now process with external tools
cat findings.json | jq 'length'
```

### Aggregation, Document Lookup, and History

```bash
# Aggregation by event code
gulp-cli query aggregation incident-001 \
  --q '{"size":0,"aggs":{"by_event_code":{"terms":{"field":"event.code"}}}}'

# Get one document by _id
gulp-cli query document-get-by-id incident-001 AVY84pUBM0e5DCHhCzDq

# Max/min timeline boundaries
gulp-cli query max-min-per-field incident-001 --group-by event.code

# Query history for authenticated user
gulp-cli query history-get
```

---

## Sigma Rule Queries

### Run Single Sigma Rule

```bash
# Detect process creation events matching rule
gulp-cli query sigma incident-001 \
  --rule-file /rules/process_creation_cmd.yml
```

### Run Rule with Severity Filtering

```bash
# Find only critical and high severity matches
gulp-cli query sigma incident-001 \
  --rule-file /rules/process_creation_cmd.yml \
  --levels critical,high
```

### Run Rule on Specific Source

```bash
# Run rule only on Security event log
gulp-cli query sigma incident-001 \
  --rule-file /rules/suspicious_activity.yml \
  --src-ids Security
```

### Multiple Sigma Rules in Batch

```bash
# Process multiple rule files
for rule in /rules/windows/*.yml; do
  echo "Processing: $rule"
  gulp-cli query sigma incident-001 --rule-file "$rule" --wait
done
```

---

## Enrichment & Tagging Workflows

### Tag Suspicious Events

```bash
# Tag all process creation events as "needs-review"
gulp-cli enrich tag incident-001 \
  --flt '{"event_id":"4688"}' \
  --tag "needs-review"

# Tag failed logins as "security-relevant"
gulp-cli enrich tag incident-001 \
  --flt '{"event_id":"4625"}' \
  --tag "security-relevant" \
  --tag "failed-login"
```

### Apply Threat Level Classification

```bash
# Mark critical events
gulp-cli enrich update incident-001 \
  --flt '{"event_id":["4688","4672","4720"]}' \
  --fields '{"threat_level":"critical","reviewed":false}'

# Mark medium events
gulp-cli enrich update incident-001 \
  --flt '{"event_id":["4625","4634"]}' \
  --fields '{"threat_level":"medium"}'
```

### Track Analysis Progress

```bash
# Mark analyzed events
gulp-cli enrich tag incident-001 \
  --flt '{"threat_level":"critical"}' \
  --tag "analyzed"

# Remove temporary tags
gulp-cli enrich untag incident-001 \
  --flt '{"tag":"temp_analysis"}' \
  --tag "temp_analysis"
```

### Remove Enrichment Data

```bash
# Clean up temporary enrichment fields
gulp-cli enrich remove incident-001 \
  --flt '{"status":"done"}' \
  --fields "temp_field_1,temp_field_2,debug_info"
```

---

## User & Operation Management

### Create Multi-User Investigation Environment

```bash
# Create operation
gulp-cli operation create incident-2026-001 \
  --description "Critical malware incident"

# Create users for investigation team
gulp-cli user create analyst1 --password secure123 --permissions read,write
gulp-cli user create analyst2 --password secure456 --permissions read,write
gulp-cli user create reviewer --password secure789 --permissions read

# Grant access to investigation
gulp-cli operation grant-user incident-2026-001 analyst1
gulp-cli operation grant-user incident-2026-001 analyst2
gulp-cli operation grant-user incident-2026-001 reviewer

# Now each analyst can work on the operation
```

### Archive Investigation (Revoke Access)

```bash
# When investigation complete, revoke external access
gulp-cli operation revoke-user incident-2026-001 analyst1
gulp-cli operation revoke-user incident-2026-001 analyst2

# Or archive by deleting if not needed anymore
gulp-cli operation delete incident-2026-001 --confirm
```

### Inspect and Revoke User Sessions

```bash
# List all logged-in sessions (admin)
gulp-cli user session-list

# List sessions for one specific user
gulp-cli user session-list --user-id analyst1

# Revoke a session by its id
gulp-cli user session-delete token_analyst1

# Non-admin users can revoke only their own session
gulp-cli --as-user analyst1 user session-delete token_analyst1

# Run the same command using another saved CLI login
gulp-cli --as-user admin user session-list
```

---

## Advanced Workflows

### Full Forensic Investigation Pipeline

```bash
#!/bin/bash
# Complete investigation workflow script

INCIDENT="incident-2026-042"
EVIDENCE_DIR="/forensic/evidence"
RULES_DIR="/sigma-rules"

# 1. Setup
echo "Creating operation..."
gulp-cli operation create $INCIDENT \
  --description "Incident response - $(date +%Y-%m-%d)"

# 2. Ingest all evidence
echo "Ingesting Windows event logs..."
gulp-cli ingest file $INCIDENT win_evtx "$EVIDENCE_DIR/windows/**/*.evtx" --wait

echo "Ingesting syslog files..."
gulp-cli ingest file $INCIDENT syslog "$EVIDENCE_DIR/linux/**/*.log" --wait

echo "Ingesting network capture..."
gulp-cli ingest file $INCIDENT pcap "$EVIDENCE_DIR/network/*.pcap" --wait

# 3. Baseline queries
echo "Running baseline queries..."
  gulp-cli query raw $INCIDENT --q '{"query":{"match_all":{}}}' --preview > baseline.json

# 4. Run Sigma rules
echo "Executing Sigma rules..."
for rule in $RULES_DIR/*.yml; do
  gulp-cli query sigma $INCIDENT --rule-file "$rule" --wait
done

# 5. Tag findings
echo "Tagging suspicious activity..."
gulp-cli enrich tag $INCIDENT \
  --flt '{"sigma_match":true}' \
  --tag "sigma-detected" \
  --tag "requires-review"

# 6. Classify by threat level
echo "Classifying threat levels..."
gulp-cli enrich update $INCIDENT \
  --flt '{"sigma_level":"critical"}' \
  --fields '{"threat_priority":1}'

gulp-cli enrich update $INCIDENT \
  --flt '{"sigma_level":["high"]}' \
  --fields '{"threat_priority":2}'

# 7. Export results
echo "Exporting findings..."
    gulp-cli query gulp-export $INCIDENT \
      --flt '{"tags":["sigma-detected"]}' \
      --output results_${INCIDENT}.json

echo "Investigation complete. Results in results_${INCIDENT}.json"
```

### Batch Processing Multiple Operations

```bash
#!/bin/bash
# Process multiple incidents in batch

INCIDENTS=("incident-001" "incident-002" "incident-003")
PLUGIN="win_evtx"
EVIDENCE_BASE="/forensic"

for incident in "${INCIDENTS[@]}"; do
  echo "Processing $incident..."
  
  # Ingest
  gulp-cli ingest file "$incident" "$PLUGIN" \
    "$EVIDENCE_BASE/$incident/**/*.evtx" --wait
  
  # Query
  gulp-cli query raw "$incident" \
    --q '{"query":{"match_all":{}}}' \
    --output-file "${incident}_results.json"
  
  # Statistics
  COUNT=$(jq '.documents | length' "${incident}_results.json")
  echo "$incident: $COUNT documents ingested"
done
```

### Integration with External Tools

```bash
# Query with jq for complex processing
gulp-cli query raw incident-001 \
  --q '{"query":{"match_all":{}}}' \
  --output-format json | \
  jq '.documents | group_by(.source) | map({source: .[0].source, count: length})'

# Feed to grep for pattern search
gulp-cli query raw incident-001 \
  --q '{"query":{"match_all":{}}}' \
  --output-format json | \
  jq -r '.documents[].content' | \
  grep -i "malware"

# Export to CSV
gulp-cli query raw incident-001 \
  --q '{"query":{"match_all":{}}}' \
  --output-format json | \
  jq -r '.documents[] | [.timestamp, .event_id, .source] | @csv' > events.csv
```

---

## Tips & Tricks

### Use Aliases for Speed

```bash
alias gop='gulp-cli operation'
alias gq='gulp-cli query'
alias gei='gulp-cli enrich'
alias gin='gulp-cli ingest'

# Usage
gop list
gq raw my_op --q '{"query":{"match_all":{}}}'
gei tag my_op --flt '{"important":true}' --tag "reviewed"
gin file my_op win_evtx 'samples/**/*.evtx'
```

### Use Environment Variables for Repetitive Tasks

```bash
# Set default operation
export GULP_DEFAULT_OP="incident-001"

# Set output format
export GULP_OUTPUT_FORMAT="json"

# Use in scripts
gulp-cli query raw $GULP_DEFAULT_OP --q '{"query":{"match_all":{}}}'
```

### Parallel Processing with GNU Parallel

```bash
# Ingest multiple files in parallel
find /evidence -name "*.evtx" | \
  parallel gulp-cli ingest file incident-001 win_evtx {}

# Run Sigma rules in parallel
find /rules -name "*.yml" | \
  parallel gulp-cli query sigma incident-001 --rule-file {} --wait
```

### Monitor Long-Running Operations

```bash
# Run with custom timeout
gulp-cli query raw incident-001 \
  --q '{"query":{"match_all":{}}}' \
  --wait \
  --timeout 7200  # 2 hours

# Or run in background
gulp-cli ingest file incident-001 win_evtx 'samples/**/*.evtx' --wait &
JOB_PID=$!
while kill -0 $JOB_PID 2>/dev/null; do
  echo "Still processing..."
  sleep 5
done
echo "Complete!"
```

---

## Common Error Handling

```bash
#!/bin/bash
# Robust error handling

set -e  # Exit on error

trap 'echo "Error on line $LINENO"' ERR

if ! gulp-cli auth whoami > /dev/null 2>&1; then
  echo "Not authenticated. Please login first."
  gulp-cli auth login
fi

if ! gulp-cli operation get "$INCIDENT" > /dev/null 2>&1; then
  echo "Creating operation $INCIDENT..."
  gulp-cli operation create "$INCIDENT"
fi

echo "Ready for investigations!"
```

---

## User Group Workflows

### Set Up Role-Based Access

```bash
# Create analyst group with read+edit
gulp-cli user-group create analysts --permission read,edit \
  --description "Field analysts – read and annotate"

# Create ingestors group
gulp-cli user-group create ingestors --permission read,edit,ingest \
  --description "Can run ingestion pipelines"

# Add users
gulp-cli user-group add-user analysts alice
gulp-cli user-group add-user analysts bob
gulp-cli user-group add-user ingestors carol

# List groups
gulp-cli user-group list
```

### Update and Clean Up Groups

```bash
# Promote analysts to also ingest
gulp-cli user-group update analysts --permission read,edit,ingest

# Remove a user from a group
gulp-cli user-group remove-user analysts bob

# Delete a group (users are kept)
gulp-cli user-group delete ingestors
```

---

## ACL / Access Control Workflows

### Grant Operation Access to a Group

```bash
# By default operations require explicit grants
# Grant the analysts group access to an operation
gulp-cli acl add-group incident-001 --obj-type operation --group-id analysts

# Later revoke it
gulp-cli acl remove-group incident-001 --obj-type operation --group-id analysts
```

### Grant Access to Individual Users

```bash
# Grant alice access to a specific note
gulp-cli acl add-user note-123 --obj-type note --user-id alice

# Revoke
gulp-cli acl remove-user note-123 --obj-type note --user-id alice
```

### Private / Public Objects

```bash
# Make a sensitive note private (owner or admin only)
gulp-cli acl make-private note-secret --obj-type note

# Publish it back to everyone
gulp-cli acl make-public note-secret --obj-type note

# Make a link private
gulp-cli acl make-private link-456 --obj-type link
```

---

## Index Management Workflows 

### Inspect Indexes

```bash
# List all indexes
gulp-cli db list-indexes

# Full JSON output (pipe to jq)
gulp-cli --verbose db list-indexes | jq '.[].name'
```

### Refresh After Ingestion

```bash
# Force index refresh so new documents are immediately searchable
gulp-cli db refresh-index incident-001
```

### Remove a Stale Investigation (Destructive)

```bash
# Delete index AND its collab operation
gulp-cli db delete-index old-incident --yes

# Delete index only, keep the operation metadata
gulp-cli db delete-index old-incident --keep-operation --yes
```

---

## Storage Workflows

### List Stored Files

```bash
# List files for one operation
gulp-cli storage list-files --operation-id incident-001

# List files for one operation/context pair
gulp-cli storage list-files --operation-id incident-001 --context-id sdk_context

# Continue from pagination token
gulp-cli storage list-files --operation-id incident-001 --continuation-token abc123
```

### Download a File by Storage ID

```bash
gulp-cli storage get-file incident-001 \
  incident-001/context-a/source-security/System.evtx \
  --output ./downloads/System.evtx
```

### Delete Files by ID or Tags

```bash
# Delete one specific file
gulp-cli storage delete-by-id incident-001 \
  incident-001/context-a/source-security/System.evtx

# Delete all files for one operation
gulp-cli storage delete-by-tags --operation-id incident-001

# Delete files only for one context inside one operation
gulp-cli storage delete-by-tags --operation-id incident-001 --context-id sdk_context

# Global cleanup (dangerous)
gulp-cli storage delete-by-tags --all --yes
```

---

## Enhance Map and Glyph Workflows

### Create and Assign Custom Glyphs

```bash
# Create a glyph from a local icon
gulp-cli glyph create --img-path ./icons/logon.png --name glyph_logon

# List glyphs to get obj ids
gulp-cli glyph list

# Update glyph name
gulp-cli glyph update <glyph_obj_id> --name glyph_logon_v2
```

### Map Event Codes to Glyph/Color

```bash
# Map successful logon events to green
gulp-cli enhance-map create 4624 win_evtx --color '#00cc66'

# Map failed logon events to red + custom glyph
gulp-cli enhance-map create 4625 win_evtx --color '#ff3300' --glyph-id glyph_logon_v2

# List current mappings
gulp-cli enhance-map list

# Filter mappings by plugin
gulp-cli enhance-map list --flt '{"plugin":"win_evtx"}'
```

### Change or Remove a Mapping

```bash
# Change visual color for an existing mapping
gulp-cli enhance-map update <enhance_map_obj_id> --color '#ffaa00'

# Get one mapping by id
gulp-cli enhance-map get <enhance_map_obj_id>

# Delete mapping when no longer needed
gulp-cli enhance-map delete <enhance_map_obj_id>
```

---

## Extension Examples (story and sigma-zip)

> These commands are from extension APIs. They are kept separate from built-in commands to avoid confusion.

### Query Sigma Rules from ZIP (Extension)

> needs non-free `query_sigma_zip` plugin to be installed on the server, this is provided just as an example.
 
```bash
# Execute all Sigma rules inside a zip archive
gulp-cli query sigma-zip incident-001 \
  --zip-file /gulp/tests/sigma_windows_small.zip \
  --wait

# Filter rules by source and level
gulp-cli query sigma-zip incident-001 \
  --zip-file /gulp/tests/sigma_windows_small.zip \
  --src-ids security \
  --levels critical,high \
  --wait
```

### Override Built-in Extension with User Extension

```bash
# Create external extension folder
mkdir -p ~/.config/gulp-cli/extension

# Copy and customize built-in query_sigma_zip extension
cp /gulp/gulp-cli/src/gulp_cli/extension/query_sigma_zip.py \
  ~/.config/gulp-cli/extension/query_sigma_zip.py

# Next CLI startup loads external file first for same filename
gulp-cli query sigma-zip --help
```

---

### Story Extension Workflows

> needs non-free `story` plugin to be installed on the server, this is provided just as an example.

#### Create an Incident Story

```bash
gulp-cli collab story create incident-001 \
  --name "Incident timeline summary" \
  --doc-ids doc-1,doc-2,doc-3 \
  --highlight-ids hl-1,hl-2 \
  --description "Key events correlated for executive review" \
  --tags executive,summary
```

#### Update Story Content

```bash
gulp-cli collab story update story-123 \
  --name "Incident timeline summary (rev2)" \
  --doc-ids doc-1,doc-4 \
  --tags executive,final
```

#### List and Inspect Stories

```bash
# Compact table output
gulp-cli collab story list incident-001

# Full JSON output with filter
gulp-cli --verbose collab story list incident-001 \
  --flt '{"tags":["executive"]}'

# Retrieve one story by id
gulp-cli collab story get incident-001 story-123
```

---

## See Also

- [Command Reference](command-reference.md) — complete command documentation
- [Getting Started](getting-started.md) — beginner guide
- [Troubleshooting](troubleshooting-cli.md) — problem resolution
