# Assistant Tools

## todo_store.py

SQLite-backed todo store for Ocean.

### Goals
- long-term memory with disk persistence
- Python API first; avoid ad-hoc SQL during chat turns
- extensible fields for priority, risk, tags, metadata, review/follow-up
- support status lifecycle, reprioritization, focus summary, next action, blocked dependencies
- support local sync bindings for external systems

### DB path
`/home/node/.openclaw/workspace/ocean-assistant/data/assistant.sqlite3`

### Supported operations
- add
- get
- list
- search
- update
- close
- set-status
- summary --mode open
- summary --mode focus
- show-sync

## icloud_sync.py

iCloud CalDAV sync bootstrap.

### Current stage
- dry-run sync implemented
- task -> Calendar / Reminders mapping implemented
- local sync bindings persisted in SQLite
- real iCloud credentials / transport pending

### Example
```bash
python assistant_tools/icloud_sync.py dry-run-sync
python assistant_tools/icloud_sync.py show-bindings
```
