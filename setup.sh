#!/usr/bin/env bash
# Grimoire bootstrap — copies the wiki template into a project.
#
# Usage:
#   ./setup.sh                 # bootstrap wiki/ in the current directory
#   ./setup.sh /path/to/project # bootstrap wiki/ in a specific project
#
# Idempotent: exits cleanly if wiki/ already exists (no overwrite).
# Works for both humans and coding agents.

set -euo pipefail

TARGET="${1:-.}"

# Resolve script directory so we can find wiki-template/ regardless of CWD.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/wiki-template"

if [ ! -d "${TEMPLATE_DIR}" ]; then
    echo "ERROR: wiki-template/ not found at ${TEMPLATE_DIR}" >&2
    echo "Make sure you're running setup.sh from within the grimoire repo." >&2
    exit 1
fi

TARGET_WIKI="${TARGET}/wiki"

if [ -d "${TARGET_WIKI}" ]; then
    echo "wiki/ already exists at ${TARGET_WIKI}"
    echo "Nothing to bootstrap — project already has a wiki."
    exit 0
fi

mkdir -p "${TARGET}"

echo "Bootstrapping Grimoire wiki into ${TARGET_WIKI} ..."
cp -r "${TEMPLATE_DIR}" "${TARGET_WIKI}"

echo ""
echo "Done. Grimoire wiki created at ${TARGET_WIKI}"
echo ""
echo "Next steps for the agent:"
echo "  1. Read AGENTS.md for the full Grimoire workflow"
echo "  2. Ask the user: 'What does this project do?' and update the Scope section"
echo "  3. Proceed with the Pre-Work Checklist"
