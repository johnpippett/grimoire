#!/usr/bin/env bash
# Disable the named Grimoire wiki-RAG timer; optionally remove its two units.

set -euo pipefail

USER_HOME="${HOME:-}"
UNIT_DIR="${XDG_CONFIG_HOME:-${USER_HOME}/.config}/systemd/user"
SERVICE_NAME="grimoire-wiki-rag-refresh.service"
TIMER_NAME="grimoire-wiki-rag-refresh.timer"
REMOVE_FILES=0

fail() {
    printf 'disable-wiki-rag-timer: %s\n' "$*" >&2
    exit 1
}

while (($# > 0)); do
    case "$1" in
        --remove-files)
            REMOVE_FILES=1
            shift
            ;;
        --help|-h)
            printf '%s\n' 'Usage: scripts/disable-wiki-rag-timer.sh [--remove-files]'
            exit 0
            ;;
        *)
            fail "unknown argument: $1"
            ;;
    esac
done

[[ -n "${USER_HOME}" ]] || fail 'HOME is not set'

systemctl --user disable --now "${TIMER_NAME}" || true
systemctl --user daemon-reload || true

if ((REMOVE_FILES)); then
    rm -f "${UNIT_DIR}/${SERVICE_NAME}" "${UNIT_DIR}/${TIMER_NAME}"
    systemctl --user daemon-reload || true
    printf 'Removed only %s and %s\n' "${SERVICE_NAME}" "${TIMER_NAME}"
else
    printf 'Disabled %s; unit files were preserved\n' "${TIMER_NAME}"
fi
