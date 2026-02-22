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

SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
SSH_OPTS=(-i "${SSH_KEY_PATH}" -p "${SSH_PORT}" -o StrictHostKeyChecking=accept-new)

if [[ -z "${REMOTE_HOST}" ]]; then
  echo "ERROR: REMOTE_HOST is required." >&2
  exit 1
fi

if [[ -z "${SSH_KEY_PATH}" || ! -f "${SSH_KEY_PATH}" ]]; then
  echo "ERROR: SSH_KEY_PATH is missing or invalid." >&2
  exit 1
fi

echo "[INFO] Starting live migration on ${SSH_TARGET}"

ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "REMOTE_STACK_DIR='${REMOTE_STACK_DIR}' COMPOSE_FILE='${COMPOSE_FILE}' bash -s" <<'EOF'
set -euo pipefail

cd "${REMOTE_STACK_DIR}"

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found in remote stack dir" >&2
  exit 1
fi

tmp_env="$(mktemp)"
sed 's/\r$//' .env > "${tmp_env}"
set -a
# shellcheck disable=SC1090
source "${tmp_env}"
set +a
rm -f "${tmp_env}"

: "${SOURCE_DB_URL:?SOURCE_DB_URL must be set in remote .env}"
: "${DATABASE_URL:?DATABASE_URL must be set in remote .env}"

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "ERROR: pg_dump not found on remote host. Install postgresql-client." >&2
  exit 1
fi

if ! command -v pg_restore >/dev/null 2>&1; then
  echo "ERROR: pg_restore not found on remote host. Install postgresql-client." >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql not found on remote host. Install postgresql-client." >&2
  exit 1
fi

WORKDIR="/tmp/ai_gateway_cutover_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${WORKDIR}"

# Stop write traffic during migration
if docker compose -f "${COMPOSE_FILE}" ps ai_gateway_service >/dev/null 2>&1; then
  docker compose -f "${COMPOSE_FILE}" stop ai_gateway_service frontend_dashboard || true
fi

echo "[INFO] Dumping source database"
pg_dump "${SOURCE_DB_URL}" -Fc -f "${WORKDIR}/source.dump"

echo "[INFO] Restoring into target PostgreSQL"
pg_restore --clean --if-exists --no-owner --no-privileges -d "${DATABASE_URL}" "${WORKDIR}/source.dump"

echo "[INFO] Applying gateway migrations"
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f db/migrations/0000_core_business_tables.sql
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f db/migrations/0001_schema_gateway.sql
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f db/migrations/0002_fk_and_indexes.sql
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f db/migrations/0003_seed_gateway_users_from_legacy.sql

echo "[INFO] Migration completed. Use ops/verify_postgres_cutover.sh before enabling traffic."
EOF

echo "[SUCCESS] migrate_live_supabase_to_postgres.sh finished"
