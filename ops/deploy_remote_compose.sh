#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS_ENV_FILE="${OPS_ENV_FILE:-${SCRIPT_DIR}/.env}"

source_env_safely() {
  local env_file="$1"
  local tmp_env
  tmp_env="$(mktemp)"
  sed 's/\r$//' "${env_file}" > "${tmp_env}"
  set -a
  # shellcheck disable=SC1090
  source "${tmp_env}"
  set +a
  rm -f "${tmp_env}"
}

if [[ -f "${OPS_ENV_FILE}" ]]; then
  source_env_safely "${OPS_ENV_FILE}"
fi

REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
SSH_PORT="${SSH_PORT:-22}"
SSH_KEY_PATH="${SSH_KEY_PATH:-}"
REMOTE_STACK_DIR="${REMOTE_STACK_DIR:-/opt/stacks/ai_model_gateway}"
COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml}"
DEPLOY_MODE="${DEPLOY_MODE:-git}" # git | rsync
GIT_BRANCH="${GIT_BRANCH:-}"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-false}"
HEALTH_PATH="${HEALTH_PATH:-/api/v1/health}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-180}"

LOCAL_STACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") [options]

Options:
  --host <host>                 Remote host (default: value from ops/.env)
  --user <user>                 Remote user (default: ${REMOTE_USER})
  --port <port>                 SSH port (default: ${SSH_PORT})
  --key <path>                  SSH private key path (default: value from ops/.env)
  --stack-dir <path>            Remote stack directory (default: ${REMOTE_STACK_DIR})
  --compose-file <file>         Compose file name in stack dir (default: ${COMPOSE_FILE})
  --deploy-mode <git|rsync>     Sync mode before deploy (default: ${DEPLOY_MODE})
  --branch <name>               Git branch for remote checkout (optional, git mode only)
  --skip-git-pull               Skip "git fetch/pull" on remote (git mode only)
  --health-path <path>          Health endpoint path (default: ${HEALTH_PATH})
  --health-timeout <seconds>    Health wait timeout (default: ${HEALTH_TIMEOUT_SECONDS})
  -h, --help                    Show this help

Examples:
  cp ops/.env.example ops/.env
  $(basename "$0")
  $(basename "$0") --deploy-mode rsync
  $(basename "$0") --branch main --health-timeout 240
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      REMOTE_HOST="$2"
      shift 2
      ;;
    --user)
      REMOTE_USER="$2"
      shift 2
      ;;
    --port)
      SSH_PORT="$2"
      shift 2
      ;;
    --key)
      SSH_KEY_PATH="$2"
      shift 2
      ;;
    --stack-dir)
      REMOTE_STACK_DIR="$2"
      shift 2
      ;;
    --compose-file)
      COMPOSE_FILE="$2"
      shift 2
      ;;
    --deploy-mode)
      DEPLOY_MODE="$2"
      shift 2
      ;;
    --branch)
      GIT_BRANCH="$2"
      shift 2
      ;;
    --skip-git-pull)
      SKIP_GIT_PULL="true"
      shift
      ;;
    --health-path)
      HEALTH_PATH="$2"
      shift 2
      ;;
    --health-timeout)
      HEALTH_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "${DEPLOY_MODE}" != "git" && "${DEPLOY_MODE}" != "rsync" ]]; then
  echo "ERROR: --deploy-mode must be 'git' or 'rsync'." >&2
  exit 1
fi

if [[ -z "${REMOTE_HOST}" ]]; then
  echo "ERROR: REMOTE_HOST is empty. Set it in ops/.env or pass --host." >&2
  exit 1
fi

if [[ ! -f "${SSH_KEY_PATH}" ]]; then
  echo "ERROR: SSH key not found. Set SSH_KEY_PATH in ops/.env or pass --key." >&2
  exit 1
fi

if ! [[ "${HEALTH_TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --health-timeout must be an integer." >&2
  exit 1
fi

SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
SSH_OPTS=(-i "${SSH_KEY_PATH}" -p "${SSH_PORT}" -o StrictHostKeyChecking=accept-new)

echo "[INFO] Target: ${SSH_TARGET}"
echo "[INFO] Remote stack: ${REMOTE_STACK_DIR}"
echo "[INFO] Deploy mode: ${DEPLOY_MODE}"

if [[ "${DEPLOY_MODE}" == "rsync" ]]; then
  echo "[INFO] Syncing local project to remote via rsync..."
  RSYNC_SSH="ssh -i \"${SSH_KEY_PATH}\" -p \"${SSH_PORT}\" -o StrictHostKeyChecking=accept-new"

  rsync -az --delete \
    --exclude ".git" \
    --exclude ".idea" \
    --exclude ".venv" \
    --exclude "__pycache__" \
    --exclude "logs" \
    --exclude "frontend/user-dashboard/node_modules" \
    -e "${RSYNC_SSH}" \
    "${LOCAL_STACK_DIR}/" "${SSH_TARGET}:${REMOTE_STACK_DIR}/"
fi

if [[ "${DEPLOY_MODE}" == "git" ]]; then
  echo "[INFO] Preparing remote git workspace..."
  ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "bash -s" <<EOF
set -euo pipefail
cd "${REMOTE_STACK_DIR}"
if [ ! -d .git ]; then
  echo "ERROR: ${REMOTE_STACK_DIR} is not a git repository. Use --deploy-mode rsync."
  exit 1
fi
if [ -n "${GIT_BRANCH}" ]; then
  git checkout "${GIT_BRANCH}"
fi
if [ "${SKIP_GIT_PULL}" != "true" ]; then
  git fetch --all --prune
  git pull --ff-only
fi
EOF
fi

echo "[INFO] Running docker compose down + up --build..."
ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "bash -s" <<EOF
set -euo pipefail
cd "${REMOTE_STACK_DIR}"
docker compose -f "${COMPOSE_FILE}" down
docker compose -f "${COMPOSE_FILE}" up -d --build
docker compose -f "${COMPOSE_FILE}" ps
EOF

echo "[INFO] Waiting for health endpoint: ${HEALTH_PATH}"
ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "bash -s" <<EOF
set -euo pipefail
cd "${REMOTE_STACK_DIR}"
deadline=\$((\$(date +%s) + ${HEALTH_TIMEOUT_SECONDS}))
while [ "\$(date +%s)" -lt "\${deadline}" ]; do
  if curl -fsS "http://127.0.0.1:6161${HEALTH_PATH}" >/dev/null; then
    echo "[INFO] Health check passed."
    exit 0
  fi
  sleep 3
done
echo "[ERROR] Health check failed after ${HEALTH_TIMEOUT_SECONDS}s."
docker compose -f "${COMPOSE_FILE}" logs --no-color --tail=120 ai_gateway_service || true
exit 1
EOF

echo "[SUCCESS] Deploy completed."
