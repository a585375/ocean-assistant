# iCloud CalDAV Sync Plan

## 目标
把 Ocean 的结构化任务系统与 iPhone 侧可见的 Calendar / Reminders 建立单向同步。

## 当前对齐结论
- 两个都要：Calendar + Reminders
- 先做单向同步
- 同步范围：所有 open task

## 总体架构
- 主系统：ocean-assistant（SQLite + knowledge base）
- iCloud Calendar：承接有明确时间的事项
- iCloud Reminders：承接所有 open task
- 数据方向：assistant -> iCloud

## 同步规则
### Calendar
同步条件：
- task 有明确时间（如 due_at 或 event time）
- 适合在日历视图中查看

映射建议：
- title -> event title
- details / next_action / risk / checklist_path -> event notes
- due_at -> event start time
- 默认提醒 -> 提前 10 分钟

### Reminders
同步条件：
- 所有 open task

映射建议：
- title -> reminder title
- details / next_action / project / risk / checklist_path -> reminder notes
- due_at -> due date（如果有）
- status=open -> 同步存在
- status=done/cancelled -> 标完成或删除（待定）

## 字段映射建议
### Task -> Calendar / Reminders
- id: 写入 notes 作为外部关联键
- title: 标题
- content/details: 备注正文
- priority: 备注中保留
- risk: 备注中保留
- project: 备注中保留
- next_step / next_action: 备注中保留
- checklist_path: 备注中保留
- due_at: Calendar 时间 / Reminder 截止时间

## 技术路径
### Calendar
- 优先走 CalDAV / iCalendar 兼容方式
- 需要 Apple ID + app-specific password
- 预期兼容性较好

### Reminders
- 需要验证 CalDAV 对 reminders / VTODO 的兼容实现
- 可能存在客户端库差异
- 需要做小范围验证后再决定最终接法

## 风险与限制
1. Calendar 通常比 Reminders 更稳
2. Reminders 的协议兼容性需要实际测试
3. 单向同步第一版更稳，先不做双向写回
4. 需要避免重复同步，需保留外部映射 id

## 第一版建议
1. 先完成 Calendar 同步
2. 再验证 Reminders 同步
3. 建立 task -> external_id 映射
4. 默认提醒策略：明确时间事项提前 10 分钟

## 待确认问题
1. done/cancelled 的 task 在 Reminders 中是标完成还是直接删除？
2. Calendar 是否需要单独日历，例如 `Ocean Assistant`？
3. Reminders 是否需要单独列表，例如 `Ocean Tasks`？
4. checklist_path 在移动端备注里要不要保留完整路径？
