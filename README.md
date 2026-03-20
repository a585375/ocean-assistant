# ocean-assistant

Ocean 的私人助理仓库。

主要用于：
- 长期记忆
- 待办事项管理
- 优先级 / 风险评估
- SQLite 落盘
- 助理侧工具与配置

当前核心组件：
- `assistant_tools/todo_store.py`：SQLite-backed todo store
- `memory/`：阶段性记忆与工作记录
- `data/`：本地数据库（默认不入库）

说明：
- 查询待办时优先通过 Python 访问层，不临时拼 SQL。
- 数据库文件默认忽略，不直接提交到 git。
