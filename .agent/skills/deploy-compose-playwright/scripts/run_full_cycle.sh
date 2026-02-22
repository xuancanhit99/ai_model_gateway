#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"

"${ROOT_DIR}/ops/deploy_remote_compose.sh" "$@"
"${ROOT_DIR}/ops/smoke_after_deploy.sh"
