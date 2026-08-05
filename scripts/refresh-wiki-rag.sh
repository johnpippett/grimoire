#!/usr/bin/env bash
# Refresh every discovered project index without changing Hermes or source docs.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
CONFIG_PATH="${GRIMOIRE_WIKI_RAG_CONFIG:-${PROJECT_DIR}/config/wiki-rag.env}"

if [[ -f "${CONFIG_PATH}" ]]; then
    # The local config is intentionally ignored by Git and is operator-owned.
    set -a
    # shellcheck disable=SC1090
    source "${CONFIG_PATH}"
    set +a
fi

PROJECTS_ROOT="${WIKI_RAG_PROJECTS_ROOT:-}"
INDEX_HOME="${WIKI_RAG_HOME:-${HOME:-}/.wiki-rag}"

fail() {
    printf 'refresh-wiki-rag: %s\n' "$*" >&2
    exit 1
}

[[ -n "${PROJECTS_ROOT}" ]] || fail "set WIKI_RAG_PROJECTS_ROOT in ${CONFIG_PATH}"
[[ -d "${PROJECTS_ROOT}" ]] || fail "project root is not a directory: ${PROJECTS_ROOT}"
[[ -d "${PROJECT_DIR}/grimoire-mcp" ]] || fail "missing grimoire-mcp package under ${PROJECT_DIR}"

if [[ -n "${UV_BIN:-}" ]]; then
    RESOLVED_UV="${UV_BIN}"
elif command -v uv >/dev/null 2>&1; then
    RESOLVED_UV="$(command -v uv)"
elif [[ -x "${HOME:-}/.local/bin/uv" ]]; then
    RESOLVED_UV="${HOME}/.local/bin/uv"
elif [[ -x "${HOME:-}/.hermes/bin/uv" ]]; then
    RESOLVED_UV="${HOME}/.hermes/bin/uv"
else
    fail "uv was not found; set UV_BIN in ${CONFIG_PATH}"
fi

[[ -x "${RESOLVED_UV}" ]] || fail "uv is not executable: ${RESOLVED_UV}"

if [[ "${GRIMOIRE_WIKI_RAG_DRY_RUN:-0}" == "1" ]]; then
    printf 'project_dir=%s\n' "${PROJECT_DIR}"
    printf 'projects_root=%s\n' "${PROJECTS_ROOT}"
    printf 'index_home=%s\n' "${INDEX_HOME}"
    printf 'uv=%s\n' "${RESOLVED_UV}"
    printf 'command=%q run --directory %q grimoire-mcp reindex %q\n' \
        "${RESOLVED_UV}" "${PROJECT_DIR}/grimoire-mcp" '*'
    exit 0
fi

mkdir -p "${INDEX_HOME}/indexes" "${INDEX_HOME}/logs"
LOG_PATH="${INDEX_HOME}/logs/refresh.log"
exec > >(tee -a "${LOG_PATH}") 2>&1

printf '\n[%s] starting Grimoire wiki-RAG refresh\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
printf 'project_dir=%s\n' "${PROJECT_DIR}"
printf 'projects_root=%s\n' "${PROJECTS_ROOT}"
printf 'index_home=%s\n' "${INDEX_HOME}"
printf 'uv=%s\n' "${RESOLVED_UV}"

export WIKI_RAG_PROJECTS_ROOT="${PROJECTS_ROOT}"
export WIKI_RAG_HOME="${INDEX_HOME}"
"${RESOLVED_UV}" run \
    --directory "${PROJECT_DIR}/grimoire-mcp" \
    grimoire-mcp reindex '*'

printf '[%s] refresh complete\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
