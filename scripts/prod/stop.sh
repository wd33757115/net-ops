#!/usr/bin/env bash
# 生产环境 - 关闭（Linux）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/deployment/docker-compose.yml"

echo "============================================================"
echo "  NetOps 生产环境 - 关闭"
echo "============================================================"

cd "$PROJECT_ROOT"

if [[ "${1:-}" == "--volumes" ]]; then
  docker compose -f "$COMPOSE_FILE" down -v
else
  docker compose -f "$COMPOSE_FILE" down
fi

echo "[完成] 生产环境已关闭"
