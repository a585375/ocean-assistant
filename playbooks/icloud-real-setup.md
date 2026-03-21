# iCloud Real Setup

## 目标
把 Ocean assistant 的任务系统真实接入 iCloud Calendar / Reminders。

## 你需要准备
1. Apple ID
2. App 专用密码
3. 确认 iCloud 日历 / 提醒事项已启用

## 配置文件
复制模板：
- `config/icloud_sync.json.template`

生成：
- `config/icloud_sync.json`

填写内容：
- `username`：Apple ID 邮箱
- `app_specific_password`：App 专用密码
- `calendar_name`：建议 `Ocean Assistant`
- `reminders_list_name`：建议 `Ocean Tasks`
- `sync_calendar`：建议先设为 `true`
- `sync_reminders`：若 Reminders 兼容性有问题，可先设为 `false`

## 环境依赖
需要安装：
- `caldav`
- `icalendar`

## 建议执行顺序
1. 先安装依赖
2. 写好 `config/icloud_sync.json`
3. 先运行 `validate-config`
4. 先做 Calendar 小样本测试
5. 再测试 Reminders

## 命令
```bash
python assistant_tools/icloud_sync.py validate-config
python assistant_tools/icloud_sync.py dry-run-sync
python assistant_tools/icloud_sync.py sync
```

## 建议策略
- 先确认 Calendar 可以成功写入
- 再确认 Reminders 的真实兼容性
- 有问题时，先保底用 Calendar

## 风险提醒
- App 专用密码不要提交到 git
- `config/icloud_sync.json` 应该加入忽略
- Reminders 真实同步可能比 Calendar 更不稳定
