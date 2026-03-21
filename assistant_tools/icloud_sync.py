from __future__ import annotations

"""iCloud CalDAV sync bootstrap for Ocean assistant.

Phase 1 goals:
- read open tasks from TodoStore
- map tasks into Calendar/Reminder payloads
- maintain local sync mapping table
- support dry-run now, real CalDAV later
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assistant_tools.todo_store import TodoItem, TodoStore

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "icloud_sync.json"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "assistant.sqlite3"


@dataclass
class SyncConfig:
    enabled: bool
    icloud_url: str
    username: str
    app_specific_password: str
    calendar_name: str
    reminders_list_name: str
    reminder_minutes_before: int
    mode: str

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "SyncConfig":
        if not path.exists():
            return cls(
                enabled=False,
                icloud_url="",
                username="",
                app_specific_password="",
                calendar_name="Ocean Assistant",
                reminders_list_name="Ocean Tasks",
                reminder_minutes_before=10,
                mode="dry-run",
            )
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
        return cls(
            enabled=bool(payload.get("enabled", False)),
            icloud_url=str(payload.get("icloud_url", "") or "").strip(),
            username=str(payload.get("username", "") or "").strip(),
            app_specific_password=str(payload.get("app_specific_password", "") or "").strip(),
            calendar_name=str(payload.get("calendar_name", "Ocean Assistant") or "Ocean Assistant").strip(),
            reminders_list_name=str(payload.get("reminders_list_name", "Ocean Tasks") or "Ocean Tasks").strip(),
            reminder_minutes_before=int(payload.get("reminder_minutes_before", 10) or 10),
            mode=str(payload.get("mode", "dry-run") or "dry-run").strip(),
        )


def build_notes(item: TodoItem) -> str:
    checklist_path = str(item.metadata.get("checklist_path", "") or "").strip()
    lines = [
        f"task_id: {item.id}",
        f"项目: {item.project or '-'}",
        f"优先级: {item.priority}",
        f"风险: {item.risk}",
        f"分类: {item.category}",
    ]
    if item.details:
        lines.append(f"内容: {item.details}")
    if item.next_action:
        lines.append(f"下一步: {item.next_action}")
    if checklist_path:
        lines.append(f"checklist: {checklist_path}")
    return "\n".join(lines)


def map_task_to_calendar(item: TodoItem, config: SyncConfig) -> dict[str, Any] | None:
    if not item.due_at:
        return None
    return {
        "kind": "calendar",
        "task_id": item.id,
        "external_key": f"calendar:{item.id}",
        "calendar_name": config.calendar_name,
        "title": item.title,
        "start_at": item.due_at,
        "alarm_minutes_before": config.reminder_minutes_before,
        "notes": build_notes(item),
    }


def map_task_to_reminder(item: TodoItem, config: SyncConfig) -> dict[str, Any]:
    return {
        "kind": "reminder",
        "task_id": item.id,
        "external_key": f"reminder:{item.id}",
        "list_name": config.reminders_list_name,
        "title": item.title,
        "due_at": item.due_at,
        "notes": build_notes(item),
        "alarm_minutes_before": config.reminder_minutes_before if item.due_at else None,
    }


class DryRunSyncAdapter:
    def upsert_calendar_event(self, payload: dict[str, Any]) -> str:
        return f"dryrun-calendar-{payload['task_id']}"

    def upsert_reminder(self, payload: dict[str, Any]) -> str:
        return f"dryrun-reminder-{payload['task_id']}"


class ICloudSyncService:
    def __init__(self, store: TodoStore, config: SyncConfig) -> None:
        self.store = store
        self.config = config
        self.adapter = DryRunSyncAdapter()

    def sync_open_tasks(self) -> dict[str, Any]:
        tasks = self.store.list_todos(status="open", limit=500)
        summary = {
            "mode": self.config.mode,
            "open_tasks": len(tasks),
            "calendar_synced": 0,
            "reminders_synced": 0,
            "calendar_payloads": [],
            "reminder_payloads": [],
        }
        for item in tasks:
            reminder_payload = map_task_to_reminder(item, self.config)
            reminder_external_id = self.adapter.upsert_reminder(reminder_payload)
            self.store.upsert_sync_binding(
                task_id=item.id,
                target_kind="reminder",
                external_id=reminder_external_id,
                external_key=str(reminder_payload["external_key"]),
                payload=reminder_payload,
            )
            summary["reminders_synced"] += 1
            summary["reminder_payloads"].append(reminder_payload)

            calendar_payload = map_task_to_calendar(item, self.config)
            if calendar_payload is not None:
                calendar_external_id = self.adapter.upsert_calendar_event(calendar_payload)
                self.store.upsert_sync_binding(
                    task_id=item.id,
                    target_kind="calendar",
                    external_id=calendar_external_id,
                    external_key=str(calendar_payload["external_key"]),
                    payload=calendar_payload,
                )
                summary["calendar_synced"] += 1
                summary["calendar_payloads"].append(calendar_payload)
        return summary


def _cli() -> None:
    parser = argparse.ArgumentParser(description="iCloud CalDAV sync bootstrap")
    parser.add_argument("command", choices=["dry-run-sync", "show-bindings"])
    args = parser.parse_args()

    store = TodoStore(DB_PATH)
    config = SyncConfig.load(CONFIG_PATH)

    if args.command == "dry-run-sync":
        service = ICloudSyncService(store, config)
        print(json.dumps(service.sync_open_tasks(), ensure_ascii=False, indent=2))
    elif args.command == "show-bindings":
        print(json.dumps(store.list_sync_bindings(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
