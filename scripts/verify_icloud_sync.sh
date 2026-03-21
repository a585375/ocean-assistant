#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "== validate-config =="
python3 assistant_tools/icloud_sync.py validate-config

echo
echo "== dry-run-sync =="
python3 assistant_tools/icloud_sync.py dry-run-sync

echo
echo "== show-bindings =="
python3 assistant_tools/icloud_sync.py show-bindings

echo
echo "验证完成。若配置无误且依赖已安装，可继续执行真实 sync。"
