#!/bin/bash
# ZGX AI Bridge - start script
# Usage: ./start.sh
# Override defaults with environment variables:
#   VLLM_BASE_URL=http://192.168.10.123:8090/v1 ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Defaults (override via env vars)
export BRIDGE_HOST="${BRIDGE_HOST:-0.0.0.0}"
export BRIDGE_PORT="${BRIDGE_PORT:-8080}"
export BRIDGE_LOG_LEVEL="${BRIDGE_LOG_LEVEL:-info}"
export VLLM_BASE_URL="${VLLM_BASE_URL:-http://localhost:8090/v1}"
export VLLM_MODEL="${VLLM_MODEL:-Qwen/Qwen3-14B-AWQ}"
export BRIDGE_API_KEYS="${BRIDGE_API_KEYS:-dev-test-key}"

echo "================================================"
echo "  ZGX AI Bridge"
echo "  Bridge:  http://${BRIDGE_HOST}:${BRIDGE_PORT}"
echo "  vLLM:    ${VLLM_BASE_URL}"
echo "  Model:   ${VLLM_MODEL}"
echo "================================================"

cd "$SCRIPT_DIR"

uvicorn bridge.main:app \
    --host "$BRIDGE_HOST" \
    --port "$BRIDGE_PORT" \
    --log-level "$BRIDGE_LOG_LEVEL"
