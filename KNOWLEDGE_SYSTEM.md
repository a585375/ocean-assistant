# Knowledge System

这是 Ocean 的个人知识库 / 外置大脑骨架。

## 目标

把助理系统从“记待办”升级为：
- 任务中枢
- 长期记忆中枢
- 项目知识库
- 决策记录库
- 复盘归因库
- 操作手册库

## 目录说明

- `assistant_tools/`：助理工具与访问层
- `memory/`：阶段性记忆
- `projects/`：项目级知识
- `decisions/`：决策记录
- `reviews/`：复盘总结
- `playbooks/`：可复用操作手册
- `checklists/`：任务执行清单
- `data/`：本地数据库（默认不入库）

## 使用原则

1. 任务要结构化
2. 重要知识要落文档
3. 文档尽量能被任务引用
4. 复盘要能回流成经验
5. 重复流程要沉淀为 playbook

## 推荐关系

- task -> checklist
- task -> output(review/decision)
- project -> risks/open questions/context
- decision -> project
- review -> project
- playbook -> recurring workflow

## 下一步

优先从 AutoTrade 开始，把项目背景、风险、复盘和关键决策逐步沉淀进去。
