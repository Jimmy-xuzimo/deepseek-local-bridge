#!/usr/bin/env bash
# macOS / Linux 一键启动
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/scripts/run.sh" "$@"
