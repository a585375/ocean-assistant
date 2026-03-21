#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install --upgrade pip
python3 -m pip install caldav icalendar

echo "依赖安装完成：caldav, icalendar"
echo "下一步："
echo "1. 复制 config/icloud_sync.json.template 为 config/icloud_sync.json"
echo "2. 填入 Apple ID 和 app 专用密码"
echo "3. 运行: python assistant_tools/icloud_sync.py validate-config"
