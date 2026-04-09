#!/usr/bin/env bash
# SessionStart hook for rocketsmith extension
# Runs dependency check and injects status into agent context.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Run dependency check via CLI; fall back gracefully if uv/rocketsmith not available
dep_status=$(uv run --directory "${PLUGIN_ROOT}" rocketsmith setup check 2>/dev/null \
  || echo "# rocketsmith dependency status\nstatus: check failed — run rocketsmith setup check manually")

# Escape string for JSON embedding
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

escaped=$(escape_for_json "$dep_status")

# Gemini CLI / SDK standard format
printf '{"additionalContext": "%s"}\n' "$escaped"
exit 0
