# iCloud Reminders Implementation Notes

## 当前目标
为 Ocean assistant 补齐 iCloud Reminders 的真实同步骨架。

## 现实情况
- Calendar 事件通常更标准、更稳
- Reminders 通常对应 CalDAV 中的 VTODO / tasks 能力
- 不同库对 VTODO / tasks 的支持程度不一致
- 因此需要先补骨架，再做真实兼容性验证

## 第一版策略
- 保留 task -> reminder payload 映射
- 保留本地 sync bindings
- 真实 adapter 先暴露接口和能力检查
- 实际写入等依赖安装与账户验证后再完成

## 需要验证的点
1. 当前选用的 caldav Python 库是否支持 VTODO 创建/更新
2. iCloud 对 reminders list 的访问方式是否稳定
3. due date / notes / external id 的写入方式是否可控
4. done/cancelled 时是标完成还是删除

## 当前建议
- 先把 Calendar 真写入打通
- Reminders 保持接口级准备状态
- 真实接入前，先做小样本验证
