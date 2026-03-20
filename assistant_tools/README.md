# Assistant Tools

## todo_store.py

SQLite-backed todo store for Ocean.

### Goals
- long-term memory with disk persistence
- Python API first; avoid ad-hoc SQL during chat turns
- extensible fields for priority, risk, tags, metadata, review/follow-up
- support status lifecycle, reprioritization, focus summary, next action, blocked dependencies

### DB path
`/home/node/.openclaw/workspace/ocean-assistant/data/assistant.sqlite3`

### Supported operations
- add
- get
- list
- search
- update
- close
- summary --mode open
- summary --mode focus

### Example
```bash
python assistant_tools/todo_store.py add "检查 IB 重连" --category ops --priority high --risk high --project AutoTrade --tags ib,reliability --next-action "查看最近 24h 日志"
python assistant_tools/todo_store.py list --status open --limit 20
python assistant_tools/todo_store.py search IB
python assistant_tools/todo_store.py update <id> --status blocked --blocked-by "等待网关恢复,等待账户确认"
python assistant_tools/todo_store.py close <id>
python assistant_tools/todo_store.py summary --mode focus
```
