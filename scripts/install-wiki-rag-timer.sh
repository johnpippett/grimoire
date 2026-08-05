#!/usr/bin/env bash
# Install only the named Grimoire wiki-RAG user service and timer.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
SERVICE_TEMPLATE="${PROJECT_DIR}/ops/systemd/grimoire-wiki-rag-refresh.service.in"
TIMER_TEMPLATE="${PROJECT_DIR}/ops/systemd/grimoire-wiki-rag-refresh.timer"
USER_HOME="${HOME:-}"
UNIT_DIR="${XDG_CONFIG_HOME:-${USER_HOME}/.config}/systemd/user"
SERVICE_NAME="grimoire-wiki-rag-refresh.service"
TIMER_NAME="grimoire-wiki-rag-refresh.timer"
PROJECTS_ROOT=""
INDEX_HOME="${USER_HOME}/.wiki-rag"
UV_BIN=""

fail() {
    printf 'install-wiki-rag-timer: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage: scripts/install-wiki-rag-timer.sh --projects-root ABSOLUTE_PATH [options]

Options:
  --projects-root PATH  Required direct-child project collection root.
  --index-home PATH     Derived index/log home (default: $HOME/.wiki-rag).
  --uv-bin PATH         Explicit executable uv path.
  --help                Show this help.
EOF
}

[[ -n "${USER_HOME}" ]] || fail 'HOME is not set'

while (($# > 0)); do
    case "$1" in
        --projects-root)
            (($# >= 2)) || fail '--projects-root requires a value'
            PROJECTS_ROOT="$2"
            shift 2
            ;;
        --index-home)
            (($# >= 2)) || fail '--index-home requires a value'
            INDEX_HOME="$2"
            shift 2
            ;;
        --uv-bin)
            (($# >= 2)) || fail '--uv-bin requires a value'
            UV_BIN="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            fail "unknown argument: $1"
            ;;
    esac
done

[[ -n "${PROJECTS_ROOT}" ]] || fail '--projects-root is required'
[[ "${PROJECTS_ROOT}" == /* ]] || fail '--projects-root must be absolute'
[[ "${INDEX_HOME}" == /* ]] || fail '--index-home must be absolute'
[[ -d "${PROJECTS_ROOT}" ]] || fail "project root is not a directory: ${PROJECTS_ROOT}"
[[ -f "${SERVICE_TEMPLATE}" ]] || fail "missing service template: ${SERVICE_TEMPLATE}"
[[ -f "${TIMER_TEMPLATE}" ]] || fail "missing timer template: ${TIMER_TEMPLATE}"
[[ -x "${PROJECT_DIR}/scripts/refresh-wiki-rag.sh" ]] || fail 'refresh script is not executable'

for value in "${PROJECT_DIR}" "${PROJECTS_ROOT}" "${INDEX_HOME}"; do
    [[ "${value}" != *$'\n'* && "${value}" != *$'\r'* && "${value}" != *[[:space:]]* && "${value}" != *'"'* && "${value}" != *'\\'* && "${value}" != *'%'* ]] || \
        fail 'paths may not contain whitespace, newline, quote, backslash, or systemd specifier characters'
done

if [[ -z "${UV_BIN}" ]]; then
    if command -v uv >/dev/null 2>&1; then
        UV_BIN="$(command -v uv)"
    elif [[ -x "${USER_HOME}/.local/bin/uv" ]]; then
        UV_BIN="${USER_HOME}/.local/bin/uv"
    elif [[ -x "${USER_HOME}/.hermes/bin/uv" ]]; then
        UV_BIN="${USER_HOME}/.hermes/bin/uv"
    else
        fail 'uv was not found; pass --uv-bin PATH'
    fi
fi
[[ -x "${UV_BIN}" ]] || fail "uv is not executable: ${UV_BIN}"
[[ "${UV_BIN}" != *$'\n'* && "${UV_BIN}" != *$'\r'* && "${UV_BIN}" != *[[:space:]]* && "${UV_BIN}" != *'"'* && "${UV_BIN}" != *'\\'* && "${UV_BIN}" != *'%'* ]] || \
    fail 'uv path may not contain whitespace, newline, quote, backslash, or systemd specifier characters'

mkdir -p "${UNIT_DIR}"

SERVICE_TMP="$(mktemp "${UNIT_DIR}/.${SERVICE_NAME}.XXXXXX")"
cleanup() {
    rm -f "${SERVICE_TMP}"
}
trap cleanup EXIT

while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line//@@PROJECT_DIR@@/${PROJECT_DIR}}"
    line="${line//@@PROJECTS_ROOT@@/${PROJECTS_ROOT}}"
    line="${line//@@INDEX_HOME@@/${INDEX_HOME}}"
    line="${line//@@UV_BIN@@/${UV_BIN}}"
    printf '%s\n' "${line}"
done < "${SERVICE_TEMPLATE}" > "${SERVICE_TMP}"

chmod 0644 "${SERVICE_TMP}"
mv -f "${SERVICE_TMP}" "${UNIT_DIR}/${SERVICE_NAME}"
install -m 0644 "${TIMER_TEMPLATE}" "${UNIT_DIR}/${TIMER_NAME}"
trap - EXIT

systemctl --user daemon-reload
systemctl --user enable --now "${TIMER_NAME}"

printf 'Installed and started %s\n' "${TIMER_NAME}"
printf 'Service: %s/%s\n' "${UNIT_DIR}" "${SERVICE_NAME}"
printf 'Timer:   %s/%s\n' "${UNIT_DIR}" "${TIMER_NAME}"
