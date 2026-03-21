# ocean-assistant

Ocean 的私人助理仓库。

主要用于：
- 长期记忆
- 待办事项管理
- 优先级 / 风险评估
- SQLite 落盘
- 助理侧工具与配置
- 知识库 / 外置大脑体系
- 外部系统同步（逐步接入）

当前核心组件：
- `assistant_tools/todo_store.py`：SQLite-backed todo store
- `assistant_tools/icloud_sync.py`：iCloud CalDAV 同步第一版骨架
- `memory/`：阶段性记忆与工作记录
- `projects/`：项目 / 主题知识库
- `data/`：本地数据库（默认不入库）

说明：
- 查询待办时优先通过 Python 访问层，不临时拼 SQL。
- 数据库文件默认忽略，不直接提交到 git。
- 待办系统支持新增、查询、更新、关闭、改优先级、focus 摘要。
- 字段支持 `next_action`、`blocked_by`、`metadata`，便于后续扩展。
- iCloud 同步当前先完成了本地映射、dry-run、同步绑定表，以及 Calendar / Reminders 的真实适配器骨架。
