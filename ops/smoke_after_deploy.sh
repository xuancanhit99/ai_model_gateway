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

FRONTEND_URL="${FRONTEND_URL:-}"
API_BASE_URL="${API_BASE_URL:-}"
FRONTEND_URL="${FRONTEND_URL:-https://gateway.vnpay.dev}"
API_BASE_URL="${API_BASE_URL:-https://gateway-api.vnpay.dev}"
HEALTH_PATH="${HEALTH_PATH:-/api/v1/health}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-20}"
CHECK_DOCS="${CHECK_DOCS:-false}"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") [options]

Options:
  --frontend-url <url>      Public frontend URL (default: ${FRONTEND_URL})
  --api-base-url <url>      Public backend API base URL (default: ${API_BASE_URL})
  --health-path <path>      Health endpoint path (default: ${HEALTH_PATH})
  --timeout <seconds>       Curl timeout for each request (default: ${TIMEOUT_SECONDS})
  --check-docs <true|false> Validate /docs contains Swagger (default: ${CHECK_DOCS})
  -h, --help                Show this help

Examples:
  $(basename "$0")
  $(basename "$0") --frontend-url https://gateway.vnpay.dev --api-base-url https://gateway-api.vnpay.dev
  $(basename "$0") --frontend-url http://localhost:6060 --api-base-url http://localhost:6161
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --frontend-url)
      FRONTEND_URL="$2"
      shift 2
      ;;
    --api-base-url)
      API_BASE_URL="$2"
      shift 2
      ;;
    --health-path)
      HEALTH_PATH="$2"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --check-docs)
      CHECK_DOCS="$2"
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

if ! [[ "${TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --timeout must be an integer." >&2
  exit 1
fi

if [[ "${CHECK_DOCS}" != "true" && "${CHECK_DOCS}" != "false" ]]; then
  echo "ERROR: --check-docs must be true or false." >&2
  exit 1
fi

FRONTEND_URL="${FRONTEND_URL%/}"
API_BASE_URL="${API_BASE_URL%/}"
HEALTH_URL="${API_BASE_URL}${HEALTH_PATH}"
DOCS_URL="${API_BASE_URL}/docs"
FRONTEND_URL="${FRONTEND_URL}/"

echo "[INFO] Frontend check: ${FRONTEND_URL}"
frontend_html="$(curl -fsS --max-time "${TIMEOUT_SECONDS}" "${FRONTEND_URL}")"
if ! grep -qi "<html" <<<"${frontend_html}"; then
  echo "[ERROR] Frontend response is not HTML." >&2
  exit 1
fi

echo "[INFO] Backend health check: ${HEALTH_URL}"
health_json="$(curl -fsS --max-time "${TIMEOUT_SECONDS}" "${HEALTH_URL}")"
if command -v jq >/dev/null 2>&1; then
  health_status="$(jq -r '.status // empty' <<<"${health_json}")"
  if [[ "${health_status}" != "healthy" ]]; then
    echo "[ERROR] Health status is not healthy. Payload: ${health_json}" >&2
    exit 1
  fi
else
  if ! grep -qi '"status"[[:space:]]*:[[:space:]]*"healthy"' <<<"${health_json}"; then
    echo "[ERROR] Health status is not healthy. Payload: ${health_json}" >&2
    exit 1
  fi
fi

if [[ "${CHECK_DOCS}" == "true" ]]; then
  echo "[INFO] Swagger docs check: ${DOCS_URL}"
  docs_html="$(curl -fsS --max-time "${TIMEOUT_SECONDS}" "${DOCS_URL}")"
  if ! grep -qi "swagger" <<<"${docs_html}"; then
    echo "[ERROR] /docs does not contain Swagger page content." >&2
    exit 1
  fi
else
  echo "[INFO] Skipping /docs check (CHECK_DOCS=false)."
fi

echo "[SUCCESS] Smoke checks passed."
