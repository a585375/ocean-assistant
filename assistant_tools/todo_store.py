from __future__ import annotations

"""SQLite-backed personal assistant todo store.

Design goals:
- stable Python API so the assistant queries todos without writing ad-hoc SQL each time
- extensible schema with structured columns + JSON metadata
- lightweight CLI for manual/debug use
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import json
import sqlite3
import uuid

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "assistant.sqlite3"

PRIORITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "someday": 0}
RISK_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}
STATUS_VALUES = {"open", "in_progress", "waiting", "blocked", "done", "cancelled", "archived", "someday"}
SYNC_TARGET_VALUES = {"calendar", "reminder"}


@dataclass
class TodoItem:
    id: str
    title: str
    details: str
    category: str
    status: str
    priority: str
    risk: str
    due_at: str | None
    owner: str
    source: str
    tags: list[str]
    project: str
    actionable: bool
    energy: str
    estimate_minutes: int | None
    follow_up_at: str | None
    last_reviewed_at: str | None
    next_action: str
    blocked_by: list[str]
    created_at: str
    updated_at: str
    metadata: dict[str, Any]


class TodoStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS todo_items (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT 'general',
                    status TEXT NOT NULL DEFAULT 'open',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    risk TEXT NOT NULL DEFAULT 'unknown',
                    due_at TEXT,
                    owner TEXT NOT NULL DEFAULT 'Ocean',
                    source TEXT NOT NULL DEFAULT 'chat',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    project TEXT NOT NULL DEFAULT '',
                    actionable INTEGER NOT NULL DEFAULT 1,
                    energy TEXT NOT NULL DEFAULT 'normal',
                    estimate_minutes INTEGER,
                    follow_up_at TEXT,
                    last_reviewed_at TEXT,
                    next_action TEXT NOT NULL DEFAULT '',
                    blocked_by_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_todo_status ON todo_items(status);
                CREATE INDEX IF NOT EXISTS idx_todo_priority ON todo_items(priority);
                CREATE INDEX IF NOT EXISTS idx_todo_risk ON todo_items(risk);
                CREATE INDEX IF NOT EXISTS idx_todo_due_at ON todo_items(due_at);
                CREATE INDEX IF NOT EXISTS idx_todo_project ON todo_items(project);
                CREATE INDEX IF NOT EXISTS idx_todo_category ON todo_items(category);
                CREATE TABLE IF NOT EXISTS todo_sync_bindings (
                    task_id TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    external_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    synced_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (task_id, target_kind)
                );
                CREATE INDEX IF NOT EXISTS idx_sync_target_kind ON todo_sync_bindings(target_kind);
                CREATE INDEX IF NOT EXISTS idx_sync_external_key ON todo_sync_bindings(external_key);
                """
            )
            self._ensure_column(conn, "todo_items", "next_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "todo_items", "blocked_by_json", "TEXT NOT NULL DEFAULT '[]'")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        names = {row[1] for row in rows}
        if column not in names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_todo(
        self,
        *,
        title: str,
        details: str = "",
        category: str = "general",
        status: str = "open",
        priority: str = "medium",
        risk: str = "unknown",
        due_at: str | None = None,
        owner: str = "Ocean",
        source: str = "chat",
        tags: list[str] | None = None,
        project: str = "",
        actionable: bool = True,
        energy: str = "normal",
        estimate_minutes: int | None = None,
        follow_up_at: str | None = None,
        next_action: str = "",
        blocked_by: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        item_id = str(uuid.uuid4())
        now = self._now()
        status = self._normalize_status(status)
        priority = self._normalize_priority(priority)
        risk = self._normalize_risk(risk)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO todo_items (
                    id, title, details, category, status, priority, risk, due_at, owner, source,
                    tags_json, project, actionable, energy, estimate_minutes, follow_up_at,
                    last_reviewed_at, next_action, blocked_by_json, created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id, title.strip(), details.strip(), category.strip() or "general", status,
                    priority, risk, due_at, owner, source, json.dumps(tags or [], ensure_ascii=False),
                    project.strip(), 1 if actionable else 0, energy.strip() or "normal",
                    estimate_minutes, follow_up_at, None, next_action.strip(),
                    json.dumps(blocked_by or [], ensure_ascii=False), now, now,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return item_id

    def get_todo(self, item_id: str) -> TodoItem | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM todo_items WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def list_todos(
        self,
        *,
        status: str | None = None,
        project: str | None = None,
        priority: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[TodoItem]:
        conditions = []
        params: list[Any] = []
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if project is not None:
            conditions.append("project = ?")
            params.append(project.strip())
        if priority is not None:
            conditions.append("priority = ?")
            params.append(self._normalize_priority(priority))
        if category is not None:
            conditions.append("category = ?")
            params.append(category.strip())
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = (
            f"SELECT * FROM todo_items {where} "
            "ORDER BY "
            "CASE priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC, "
            "CASE risk WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC, "
            "COALESCE(due_at, '9999-12-31T23:59:59+00:00') ASC, "
            "updated_at DESC LIMIT ?"
        )
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_item(row) for row in rows]

    def search_todos(self, text: str, *, limit: int = 20) -> list[TodoItem]:
        pattern = f"%{text.strip()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM todo_items
                WHERE title LIKE ? OR details LIKE ? OR project LIKE ? OR tags_json LIKE ? OR metadata_json LIKE ? OR next_action LIKE ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, pattern, pattern, int(limit)),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def update_todo(self, item_id: str, **fields: Any) -> TodoItem | None:
        if not fields:
            return self.get_todo(item_id)
        allowed = {
            "title", "details", "category", "status", "priority", "risk", "due_at", "owner", "source",
            "project", "actionable", "energy", "estimate_minutes", "follow_up_at", "last_reviewed_at",
            "next_action", "metadata", "tags", "blocked_by",
        }
        payload: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "status":
                value = self._normalize_status(value)
            elif key == "priority":
                value = self._normalize_priority(value)
            elif key == "risk":
                value = self._normalize_risk(value)
            elif key == "tags":
                key = "tags_json"
                value = json.dumps(value or [], ensure_ascii=False)
            elif key == "blocked_by":
                key = "blocked_by_json"
                value = json.dumps(value or [], ensure_ascii=False)
            elif key == "metadata":
                key = "metadata_json"
                value = json.dumps(value or {}, ensure_ascii=False)
            elif key == "actionable":
                value = 1 if bool(value) else 0
            payload[key] = value
        if not payload:
            return self.get_todo(item_id)
        payload["updated_at"] = self._now()
        assignments = ", ".join(f"{k} = ?" for k in payload.keys())
        values = list(payload.values()) + [item_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE todo_items SET {assignments} WHERE id = ?", values)
        return self.get_todo(item_id)

    def set_status(self, item_id: str, status: str) -> TodoItem | None:
        patch: dict[str, Any] = {"status": status}
        normalized = self._normalize_status(status)
        if normalized in {"done", "cancelled", "archived"}:
            patch["last_reviewed_at"] = self._now()
        return self.update_todo(item_id, **patch)

    def reprioritize(self, item_id: str, *, priority: str | None = None, risk: str | None = None) -> TodoItem | None:
        patch: dict[str, Any] = {}
        if priority is not None:
            patch["priority"] = priority
        if risk is not None:
            patch["risk"] = risk
        return self.update_todo(item_id, **patch)

    def upsert_sync_binding(
        self,
        *,
        task_id: str,
        target_kind: str,
        external_id: str,
        external_key: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        normalized_target = str(target_kind or "").strip().lower()
        if normalized_target not in SYNC_TARGET_VALUES:
            raise ValueError(f"Unsupported sync target_kind: {target_kind}")
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO todo_sync_bindings (task_id, target_kind, external_id, external_key, payload_json, synced_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, target_kind) DO UPDATE SET
                    external_id = excluded.external_id,
                    external_key = excluded.external_key,
                    payload_json = excluded.payload_json,
                    synced_at = excluded.synced_at,
                    updated_at = excluded.updated_at
                """,
                (
                    task_id,
                    normalized_target,
                    str(external_id),
                    str(external_key),
                    json.dumps(payload or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def list_sync_bindings(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT task_id, target_kind, external_id, external_key, payload_json, synced_at, updated_at FROM todo_sync_bindings ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {
                "task_id": row["task_id"],
                "target_kind": row["target_kind"],
                "external_id": row["external_id"],
                "external_key": row["external_key"],
                "payload": json.loads(row["payload_json"] or "{}"),
                "synced_at": row["synced_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def summarize_open(self, *, limit: int = 10) -> dict[str, Any]:
        items = self.list_todos(status="open", limit=limit)
        with self._connect() as conn:
            counts = {row[0]: row[1] for row in conn.execute("SELECT status, COUNT(*) FROM todo_items GROUP BY status").fetchall()}
        return {"counts": counts, "top_open": [self._item_to_dict(item) for item in items]}

    def summarize_focus(self, *, limit: int = 10) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM todo_items
                WHERE status IN ('open','in_progress','blocked','waiting')
                ORDER BY
                    CASE priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC,
                    CASE risk WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC,
                    COALESCE(due_at, '9999-12-31T23:59:59+00:00') ASC,
                    updated_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        items = [self._row_to_item(row) for row in rows]
        return {
            "focus": [self._item_to_dict(item) for item in items],
            "high_priority": [self._item_to_dict(item) for item in items if item.priority in {"critical", "high"}],
            "blocked": [self._item_to_dict(item) for item in items if item.status == "blocked"],
        }

    def _normalize_status(self, value: Any) -> str:
        text = str(value or "open").strip().lower()
        return text if text in STATUS_VALUES else "open"

    def _normalize_priority(self, value: Any) -> str:
        text = str(value or "medium").strip().lower()
        return text if text in PRIORITY_ORDER else "medium"

    def _normalize_risk(self, value: Any) -> str:
        text = str(value or "unknown").strip().lower()
        return text if text in RISK_ORDER else "unknown"

    def _row_to_item(self, row: sqlite3.Row) -> TodoItem:
        return TodoItem(
            id=row["id"],
            title=row["title"],
            details=row["details"],
            category=row["category"],
            status=row["status"],
            priority=row["priority"],
            risk=row["risk"],
            due_at=row["due_at"],
            owner=row["owner"],
            source=row["source"],
            tags=json.loads(row["tags_json"] or "[]"),
            project=row["project"],
            actionable=bool(row["actionable"]),
            energy=row["energy"],
            estimate_minutes=row["estimate_minutes"],
            follow_up_at=row["follow_up_at"],
            last_reviewed_at=row["last_reviewed_at"],
            next_action=row["next_action"] if "next_action" in row.keys() else "",
            blocked_by=json.loads(row["blocked_by_json"] or "[]") if "blocked_by_json" in row.keys() else [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _item_to_dict(self, item: TodoItem) -> dict[str, Any]:
        payload = asdict(item)
        return {
            "id": payload["id"],
            "title": payload["title"],
            "details": payload["details"],
            "category": payload["category"],
            "status": payload["status"],
            "priority": payload["priority"],
            "risk": payload["risk"],
            "due_at": payload["due_at"],
            "follow_up_at": payload["follow_up_at"],
            "project": payload["project"],
            "tags": payload["tags"],
            "actionable": payload["actionable"],
            "energy": payload["energy"],
            "estimate_minutes": payload["estimate_minutes"],
            "next_action": payload["next_action"],
            "blocked_by": payload["blocked_by"],
            "created_at": payload["created_at"],
            "updated_at": payload["updated_at"],
        }


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Assistant todo store")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add")
    add.add_argument("title")
    add.add_argument("--details", default="")
    add.add_argument("--category", default="general")
    add.add_argument("--priority", default="medium")
    add.add_argument("--risk", default="unknown")
    add.add_argument("--status", default="open")
    add.add_argument("--project", default="")
    add.add_argument("--tags", default="")
    add.add_argument("--next-action", default="")
    add.add_argument("--blocked-by", default="")
    add.add_argument("--due-at", default=None)

    ls = sub.add_parser("list")
    ls.add_argument("--status", default=None)
    ls.add_argument("--project", default=None)
    ls.add_argument("--priority", default=None)
    ls.add_argument("--category", default=None)
    ls.add_argument("--limit", type=int, default=20)

    search = sub.add_parser("search")
    search.add_argument("text")
    search.add_argument("--limit", type=int, default=20)

    summary = sub.add_parser("summary")
    summary.add_argument("--mode", choices=["open", "focus"], default="open")

    get = sub.add_parser("get")
    get.add_argument("id")

    update = sub.add_parser("update")
    update.add_argument("id")
    update.add_argument("--title")
    update.add_argument("--details")
    update.add_argument("--category")
    update.add_argument("--status")
    update.add_argument("--priority")
    update.add_argument("--risk")
    update.add_argument("--project")
    update.add_argument("--next-action")
    update.add_argument("--blocked-by")
    update.add_argument("--due-at")

    close = sub.add_parser("close")
    close.add_argument("id")
    close.add_argument("--status", default="done")

    set_status = sub.add_parser("set-status")
    set_status.add_argument("id")
    set_status.add_argument("status")

    show_sync = sub.add_parser("show-sync")

    args = parser.parse_args()
    store = TodoStore()

    if args.cmd == "add":
        item_id = store.add_todo(
            title=args.title,
            details=args.details,
            category=args.category,
            priority=args.priority,
            risk=args.risk,
            status=args.status,
            project=args.project,
            tags=[t for t in args.tags.split(",") if t],
            next_action=args.next_action,
            blocked_by=[t for t in args.blocked_by.split(",") if t],
            due_at=args.due_at,
        )
        print(json.dumps({"id": item_id}, ensure_ascii=False))
    elif args.cmd == "list":
        print(json.dumps([store._item_to_dict(i) for i in store.list_todos(status=args.status, project=args.project, priority=args.priority, category=args.category, limit=args.limit)], ensure_ascii=False, indent=2))
    elif args.cmd == "search":
        print(json.dumps([store._item_to_dict(i) for i in store.search_todos(args.text, limit=args.limit)], ensure_ascii=False, indent=2))
    elif args.cmd == "summary":
        data = store.summarize_open() if args.mode == "open" else store.summarize_focus()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.cmd == "get":
        item = store.get_todo(args.id)
        print(json.dumps(asdict(item) if item else None, ensure_ascii=False, indent=2))
    elif args.cmd == "update":
        patch = {}
        for field_name, value in {
            "title": args.title,
            "details": args.details,
            "category": args.category,
            "status": args.status,
            "priority": args.priority,
            "risk": args.risk,
            "project": args.project,
            "next_action": args.next_action,
            "due_at": args.due_at,
        }.items():
            if value is not None:
                patch[field_name] = value
        if args.blocked_by is not None:
            patch["blocked_by"] = [t for t in args.blocked_by.split(",") if t] if args.blocked_by else []
        item = store.update_todo(args.id, **patch)
        print(json.dumps(asdict(item) if item else None, ensure_ascii=False, indent=2))
    elif args.cmd == "close":
        item = store.set_status(args.id, args.status)
        print(json.dumps(asdict(item) if item else None, ensure_ascii=False, indent=2))
    elif args.cmd == "set-status":
        item = store.set_status(args.id, args.status)
        print(json.dumps(asdict(item) if item else None, ensure_ascii=False, indent=2))
    elif args.cmd == "show-sync":
        print(json.dumps(store.list_sync_bindings(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
