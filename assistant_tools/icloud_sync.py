from __future__ import annotations

"""iCloud CalDAV sync bootstrap for Ocean assistant.

Current goals:
- read open tasks from TodoStore
- map tasks into Calendar/Reminder payloads
- maintain local sync mapping table
- support dry-run now and real Calendar sync when credentials + deps are ready
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
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
    sync_calendar: bool
    sync_reminders: bool

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
            sync_calendar=bool(payload.get("sync_calendar", True)),
            sync_reminders=bool(payload.get("sync_reminders", True)),
        )

    def validate(self) -> list[str]:
        issues: list[str] = []
        if self.mode not in {"dry-run", "real"}:
            issues.append("mode 只能是 dry-run 或 real")
        if self.mode == "real":
            if not self.icloud_url:
                issues.append("缺少 icloud_url")
            if not self.username:
                issues.append("缺少 username")
            if not self.app_specific_password:
                issues.append("缺少 app_specific_password")
        return issues


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


class RealCalendarSyncAdapter:
    def __init__(self, config: SyncConfig) -> None:
        self.config = config
        try:
            import caldav  # type: ignore
            from icalendar import Alarm, Calendar, Event, Todo  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "真实 iCloud 同步依赖缺失，请先安装 caldav 和 icalendar"
            ) from exc
        self._caldav = caldav
        self._Calendar = Calendar
        self._Event = Event
        self._Alarm = Alarm
        self._Todo = Todo
        self._calendar_resource = None
        self._reminders_resource = None
        self._principal = None

    def _get_principal(self):
        if self._principal is not None:
            return self._principal
        client = self._caldav.DAVClient(
            url=self.config.icloud_url,
            username=self.config.username,
            password=self.config.app_specific_password,
        )
        self._principal = client.principal()
        return self._principal

    def _get_calendar(self):
        if self._calendar_resource is not None:
            return self._calendar_resource
        principal = self._get_principal()
        calendars = principal.calendars()
        for calendar in calendars:
            try:
                name = str(calendar.get_display_name() or "").strip()
            except Exception:
                name = str(getattr(calendar, "name", "") or "").strip()
            if name == self.config.calendar_name:
                self._calendar_resource = calendar
                return calendar
        self._calendar_resource = principal.make_calendar(name=self.config.calendar_name)
        return self._calendar_resource

    def _get_reminders_collection(self):
        if self._reminders_resource is not None:
            return self._reminders_resource
        principal = self._get_principal()
        calendars = principal.calendars()
        for calendar in calendars:
            try:
                name = str(calendar.get_display_name() or "").strip()
            except Exception:
                name = str(getattr(calendar, "name", "") or "").strip()
            if name == self.config.reminders_list_name:
                self._reminders_resource = calendar
                return calendar
        self._reminders_resource = principal.make_calendar(name=self.config.reminders_list_name)
        return self._reminders_resource

    def upsert_calendar_event(self, payload: dict[str, Any]) -> str:
        calendar = self._get_calendar()
        start_at = datetime.fromisoformat(str(payload["start_at"]))
        end_at = start_at + timedelta(minutes=30)

        cal = self._Calendar()
        cal.add("prodid", "-//Ocean Assistant//iCloud Sync//CN")
        cal.add("version", "2.0")

        event = self._Event()
        uid = f"ocean-assistant-calendar-{payload['task_id']}"
        event.add("uid", uid)
        event.add("summary", payload["title"])
        event.add("dtstart", start_at)
        event.add("dtend", end_at)
        event.add("description", payload.get("notes", ""))

        minutes_before = int(payload.get("alarm_minutes_before") or 10)
        alarm = self._Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", payload["title"])
        alarm.add("trigger", timedelta(minutes=-minutes_before))
        event.add_component(alarm)
        cal.add_component(event)

        event_name = f"{uid}.ics"
        base_url = str(getattr(calendar, "url", "")).rstrip("/")
        if not base_url:
            raise RuntimeError("未获取到 iCloud calendar URL")
        event_url = f"{base_url}/{event_name}"
        response = self._principal.client.put(
            event_url,
            cal.to_ical().decode("utf-8"),
            headers={"Content-Type": "text/calendar; charset=utf-8"},
        )
        status = getattr(response, "status", None) or getattr(response, "status_code", None)
        if status not in (200, 201, 204):
            raise RuntimeError(f"Calendar PUT 失败，status={status}")
        return event_url

    def upsert_reminder(self, payload: dict[str, Any]) -> str:
        reminders = self._get_reminders_collection()

        cal = self._Calendar()
        cal.add("prodid", "-//Ocean Assistant//iCloud Sync//CN")
        cal.add("version", "2.0")

        todo = self._Todo()
        uid = f"ocean-assistant-reminder-{payload['task_id']}"
        todo.add("uid", uid)
        todo.add("summary", payload["title"])
        todo.add("description", payload.get("notes", ""))
        if payload.get("due_at"):
            todo.add("due", datetime.fromisoformat(str(payload["due_at"])))
        cal.add_component(todo)

        reminder_path = f"{uid}-{uuid4().hex}.ics"
        try:
            saved = reminders.save_todo(reminder_path, cal.to_ical())
            url = getattr(saved, "url", None)
            return str(url or reminder_path)
        except AttributeError as exc:
            raise NotImplementedError(
                "当前 caldav 库可能不支持 save_todo；需实测兼容后决定最终实现"
            ) from exc


class ICloudSyncService:
    def __init__(self, store: TodoStore, config: SyncConfig) -> None:
        self.store = store
        self.config = config
        if config.mode == "real":
            self.adapter = RealCalendarSyncAdapter(config)
        else:
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
            "warnings": [],
            "sync_calendar": self.config.sync_calendar,
            "sync_reminders": self.config.sync_reminders,
        }
        for item in tasks:
            if self.config.sync_reminders:
                reminder_payload = map_task_to_reminder(item, self.config)
                try:
                    reminder_external_id = self.adapter.upsert_reminder(reminder_payload)
                    self.store.upsert_sync_binding(
                        task_id=item.id,
                        target_kind="reminder",
                        external_id=reminder_external_id,
                        external_key=str(reminder_payload["external_key"]),
                        payload=reminder_payload,
                    )
                    summary["reminders_synced"] += 1
                except NotImplementedError:
                    summary["warnings"].append(f"提醒未同步（待实现）：{item.id}")
                summary["reminder_payloads"].append(reminder_payload)

            if self.config.sync_calendar:
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
    parser.add_argument("command", choices=["dry-run-sync", "sync", "show-bindings", "validate-config"])
    args = parser.parse_args()

    store = TodoStore(DB_PATH)
    config = SyncConfig.load(CONFIG_PATH)

    if args.command == "validate-config":
        print(json.dumps({"issues": config.validate(), "mode": config.mode}, ensure_ascii=False, indent=2))
    elif args.command in {"dry-run-sync", "sync"}:
        if args.command == "dry-run-sync":
            config.mode = "dry-run"
        issues = config.validate()
        if issues:
            print(json.dumps({"ok": False, "issues": issues}, ensure_ascii=False, indent=2))
            raise SystemExit(1)
        service = ICloudSyncService(store, config)
        print(json.dumps(service.sync_open_tasks(), ensure_ascii=False, indent=2))
    elif args.command == "show-bindings":
        print(json.dumps(store.list_sync_bindings(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
