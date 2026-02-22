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

echo "[INFO] Running cutover verification on ${SSH_TARGET}"

ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "REMOTE_STACK_DIR='${REMOTE_STACK_DIR}' bash -s" <<'EOF'
set -euo pipefail

cd "${REMOTE_STACK_DIR}"
tmp_env="$(mktemp)"
sed 's/\r$//' .env > "${tmp_env}"
set -a
# shellcheck disable=SC1090
source "${tmp_env}"
set +a
rm -f "${tmp_env}"

: "${DATABASE_URL:?DATABASE_URL must be set in remote .env}"

if command -v psql >/dev/null 2>&1; then
  run_psql() {
    local sql="$1"
    psql "${DATABASE_URL}" -c "${sql}"
  }
else
  run_psql() {
    local sql="$1"
    docker compose exec -T postgres psql \
      -U "${POSTGRES_USER:-ai_gateway}" \
      -d "${POSTGRES_DB:-ai_gateway}" \
      -c "${sql}" < /dev/null
  }
fi

echo "[INFO] Row counts"
run_psql "
SELECT 'api_keys' AS table_name, COUNT(*) AS row_count FROM public.api_keys
UNION ALL
SELECT 'user_provider_keys', COUNT(*) FROM public.user_provider_keys
UNION ALL
SELECT 'provider_key_logs', COUNT(*) FROM public.provider_key_logs
UNION ALL
SELECT 'gateway_users', COUNT(*) FROM public.gateway_users;
"

echo "[INFO] Orphan checks (must be 0)"
run_psql "
SELECT 'api_keys' AS table_name, COUNT(*) AS orphan_rows
FROM public.api_keys a
LEFT JOIN public.gateway_users gu ON gu.idsafe_sub = a.user_id
WHERE gu.idsafe_sub IS NULL
UNION ALL
SELECT 'user_provider_keys', COUNT(*)
FROM public.user_provider_keys p
LEFT JOIN public.gateway_users gu ON gu.idsafe_sub = p.user_id
WHERE gu.idsafe_sub IS NULL
UNION ALL
SELECT 'provider_key_logs', COUNT(*)
FROM public.provider_key_logs l
LEFT JOIN public.gateway_users gu ON gu.idsafe_sub = l.user_id
WHERE gu.idsafe_sub IS NULL;
"

echo "[INFO] Duplicate vnpay_id groups (must be 0)"
run_psql "
SELECT COUNT(*) AS duplicate_vnpay_id_groups
FROM (
  SELECT vnpay_id
  FROM public.gateway_users
  WHERE vnpay_id IS NOT NULL
  GROUP BY vnpay_id
  HAVING COUNT(*) > 1
) t;
"
EOF

echo "[SUCCESS] verify_postgres_cutover.sh finished"
