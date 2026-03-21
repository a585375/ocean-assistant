# iCloud Task Mapping

## 总原则
- 主数据源：ocean-assistant
- Calendar：只承接有明确时间的事项
- Reminders：承接所有 open task

## Task -> Calendar
- `title` -> event title
- `due_at` -> event start time
- `details` -> notes
- `next_action` -> notes
- `project` -> notes
- `risk` -> notes
- `checklist_path` -> notes
- `id` -> notes 中的 task_id / external_key
- 默认提醒：提前 10 分钟

## Task -> Reminders
- `title` -> reminder title
- `due_at` -> due date（如果有）
- `details` -> notes
- `next_action` -> notes
- `project` -> notes
- `risk` -> notes
- `checklist_path` -> notes
- `id` -> notes 中的 task_id / external_key

## 本地映射
系统会在 SQLite 中保存：
- task_id
- target_kind（calendar / reminder）
- external_id
- external_key
- payload_json
- synced_at
- updated_at

这样后面接入真实 iCloud 后，可以避免重复创建，并支持后续更新。
