from __future__ import annotations

"""SQLite-backed personal assistant todo store.

Design goals:
- stable Python API so the assistant queries todos without writing ad-hoc SQL each time
- extensible schema with structured columns + JSON metadata
- lightweight CLI for manual/debug use
"""

from dataclasses import dataclass
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
STATUS_VALUES = {"open", "in_progress", "blocked", "done", "cancelled", "archived"}


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
                """
            )

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
        metadata: dict[str, Any] | None = None,
    ) -> str:
        item_id = str(uuid.uuid4())
        now = self._now()
        status = status if status in STATUS_VALUES else "open"
        priority = priority if priority in PRIORITY_ORDER else "medium"
        risk = risk if risk in RISK_ORDER else "unknown"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO todo_items (
                    id, title, details, category, status, priority, risk, due_at, owner, source,
                    tags_json, project, actionable, energy, estimate_minutes, follow_up_at,
                    last_reviewed_at, created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id, title.strip(), details.strip(), category.strip() or "general", status,
                    priority, risk, due_at, owner, source, json.dumps(tags or [], ensure_ascii=False),
                    project.strip(), 1 if actionable else 0, energy.strip() or "normal",
                    estimate_minutes, follow_up_at, None, now, now,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return item_id

    def list_todos(self, *, status: str | None = None, limit: int = 20) -> list[TodoItem]:
        query = (
            "SELECT * FROM todo_items "
            "WHERE (? IS NULL OR status = ?) "
            "ORDER BY "
            "CASE priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC, "
            "CASE risk WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC, "
            "COALESCE(due_at, '9999-12-31T23:59:59+00:00') ASC, "
            "updated_at DESC LIMIT ?"
        )
        with self._connect() as conn:
            rows = conn.execute(query, (status, status, int(limit))).fetchall()
        return [self._row_to_item(row) for row in rows]

    def search_todos(self, text: str, *, limit: int = 20) -> list[TodoItem]:
        pattern = f"%{text.strip()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM todo_items
                WHERE title LIKE ? OR details LIKE ? OR project LIKE ? OR tags_json LIKE ? OR metadata_json LIKE ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, pattern, int(limit)),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def summarize_open(self, *, limit: int = 10) -> dict[str, Any]:
        items = self.list_todos(status="open", limit=limit)
        with self._connect() as conn:
            counts = {
                row[0]: row[1]
                for row in conn.execute("SELECT status, COUNT(*) FROM todo_items GROUP BY status").fetchall()
            }
        return {
            "counts": counts,
            "top_open": [self._item_to_dict(item) for item in items],
        }

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
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _item_to_dict(self, item: TodoItem) -> dict[str, Any]:
        return {
            "id": item.id,
            "title": item.title,
            "category": item.category,
            "status": item.status,
            "priority": item.priority,
            "risk": item.risk,
            "due_at": item.due_at,
            "project": item.project,
            "tags": item.tags,
            "updated_at": item.updated_at,
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
    add.add_argument("--project", default="")
    add.add_argument("--tags", default="")

    ls = sub.add_parser("list")
    ls.add_argument("--status", default=None)
    ls.add_argument("--limit", type=int, default=20)

    search = sub.add_parser("search")
    search.add_argument("text")
    search.add_argument("--limit", type=int, default=20)

    sub.add_parser("summary")

    args = parser.parse_args()
    store = TodoStore()

    if args.cmd == "add":
        item_id = store.add_todo(
            title=args.title,
            details=args.details,
            category=args.category,
            priority=args.priority,
            risk=args.risk,
            project=args.project,
            tags=[t for t in args.tags.split(",") if t],
        )
        print(json.dumps({"id": item_id}, ensure_ascii=False))
    elif args.cmd == "list":
        print(json.dumps([store._item_to_dict(i) for i in store.list_todos(status=args.status, limit=args.limit)], ensure_ascii=False, indent=2))
    elif args.cmd == "search":
        print(json.dumps([store._item_to_dict(i) for i in store.search_todos(args.text, limit=args.limit)], ensure_ascii=False, indent=2))
    elif args.cmd == "summary":
        print(json.dumps(store.summarize_open(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
