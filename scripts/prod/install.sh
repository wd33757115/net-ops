#!/usr/bin/env bash
# 生产环境 - 安装与部署（Linux）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/deployment/docker-compose.yml"

echo "============================================================"
echo "  NetOps 生产环境 - 安装部署 (Linux)"
echo "============================================================"

cd "$PROJECT_ROOT"

if ! command -v docker &>/dev/null; then
  echo "[ERROR] 需要 Docker Engine" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cat > .env <<'EOF'
DEBUG=false
ENFORCE_BFF_ORIGIN=true
USE_SUPERVISOR_V2=true
DEEPSEEK_API_KEY=
POSTGRES_PASSWORD=netops123456
DJANGO_SECRET_KEY=change-me-in-production
EOF
  echo "[WARN] .env 已创建，请修改密钥"
fi

docker compose -f "$COMPOSE_FILE" pull postgres redis rabbitmq minio qdrant
docker compose -f "$COMPOSE_FILE" build django react
mkdir -p "$PROJECT_ROOT/deployment/qdrant_storage"

echo "[完成] 生产环境安装部署完成"
