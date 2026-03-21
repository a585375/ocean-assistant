# iCloud Validation Checklist

## 接入前检查
- [ ] 已安装 `caldav`
- [ ] 已安装 `icalendar`
- [ ] 已创建 `config/icloud_sync.json`
- [ ] 已填写 Apple ID
- [ ] 已填写 app 专用密码
- [ ] 已确认 iCloud Calendar / Reminders 已启用

## 命令顺序
1. `python assistant_tools/icloud_sync.py validate-config`
2. `python assistant_tools/icloud_sync.py dry-run-sync`
3. `python assistant_tools/icloud_sync.py show-bindings`
4. `python assistant_tools/icloud_sync.py sync`

## 验证重点
- Calendar 是否成功创建事件
- iPhone 是否可见同步后的内容
- Reminders 是否可正常创建
- 是否出现重复创建
- 备注中是否保留 task_id / project / next_action / checklist

## 当前建议
- 先验证 Calendar
- Reminders 单独小样本验证
