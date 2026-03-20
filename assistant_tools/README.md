# Assistant Tools

## todo_store.py

SQLite-backed todo store for Ocean.

### Goals
- long-term memory with disk persistence
- Python API first; avoid ad-hoc SQL during chat turns
- extensible fields for priority, risk, tags, metadata, review/follow-up

### DB path
`/home/node/.openclaw/workspace/data/assistant.sqlite3`

### Example
```bash
python assistant_tools/todo_store.py add "检查 IB 重连" --category ops --priority high --risk high --project AutoTrade --tags ib,reliability
python assistant_tools/todo_store.py summary
python assistant_tools/todo_store.py list --status open --limit 20
python assistant_tools/todo_store.py search IB
```
