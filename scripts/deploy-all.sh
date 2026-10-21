#!/usr/bin/env bash
# Prepare + deploy every Texas Tech agent.
#
# Phase 1 (parallel): scripts/prepare-deploy.sh <agent> for every agent, as background
#   jobs — the slow, side-effect-free part (refreshing config_cache.json from the live
#   sheet, vendoring patterns/ deps, regenerating uv.lock). Safe to run concurrently.
# Phase 2 (parallel, one Terminal.app window per agent): guava deploy up <agent>/deploy,
#   for every agent whose prepare succeeded — each in its own new Terminal window, so you
#   can answer all their confirmation prompts side by side instead of one at a time.
#
#   guava deploy up asks for an interactive confirmation before pushing — there's no
#   --yes/--force flag for it (unlike the destructive `guava deploy purge`, which has
#   one). That confirmation hard-fails ("Confirmation failed: ... not a terminal") with
#   no TTY, and bash auto-redirects a backgrounded job's stdin to /dev/null — so it can't
#   be scripted through silently in this process. Each spawned Terminal window gets a real
#   TTY of its own instead, so its prompt works normally and you approve it there.
#
#   macOS only (osascript + Terminal.app).
#
# Usage:
#   ./scripts/deploy-all.sh                          # all 4 agents
#   ./scripts/deploy-all.sh inbound-10k inbound-k12   # a subset
#
# guava.toml's org_id is only honored when a project is first created; every deploy after
# that actually targets the CLI session's currently active org (`guava org use`), NOT
# necessarily the org baked into guava.toml — see gotchas/deploy-auth.md. All 4 agents here
# share one org, so this switches to it once, up front.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

ALL_AGENTS=(inbound-10k inbound-grad inbound-k12 inbound-online)
if [[ $# -gt 0 ]]; then
  AGENTS=("$@")
else
  AGENTS=("${ALL_AGENTS[@]}")
fi

# ── Resolve the shared org_id and validate every agent agrees on it ─────────────
ORG_ID=""
for agent in "${AGENTS[@]}"; do
  TOML="$REPO_ROOT/$agent/deploy/guava.toml"
  if [[ ! -f "$TOML" ]]; then
    echo "ERROR: $agent/deploy/guava.toml not found — this agent has never been deployed." >&2
    echo "       Run './scripts/prepare-deploy.sh $agent' then 'guava deploy up $agent/deploy' once" >&2
    echo "       by hand to create it, commit $agent/deploy/guava.toml, then re-run this script." >&2
    exit 1
  fi
  THIS_ORG="$(sed -n 's/^org_id *= *"\(.*\)".*/\1/p' "$TOML")"
  if [[ -z "$THIS_ORG" ]]; then
    echo "ERROR: could not read org_id from $TOML" >&2
    exit 1
  fi
  if [[ -z "$ORG_ID" ]]; then
    ORG_ID="$THIS_ORG"
  elif [[ "$THIS_ORG" != "$ORG_ID" ]]; then
    echo "ERROR: $agent's org_id ($THIS_ORG) differs from $ORG_ID." >&2
    echo "       Deploying multiple orgs in one run isn't safe — there's only one active" >&2
    echo "       org per CLI session (see gotchas/deploy-auth.md). Deploy these separately." >&2
    exit 1
  fi
done

echo "Switching active org to $ORG_ID..."
guava org use "$ORG_ID"
echo

# ── Phase 1: prepare every agent in parallel ────────────────────────────────────
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/guava-deploy-all.XXXXXX")"
echo "Prepare logs: $LOG_DIR"
echo

PIDS=()
for agent in "${AGENTS[@]}"; do
  (
    set -euo pipefail
    cd "$REPO_ROOT"
    ./scripts/prepare-deploy.sh "$agent"
  ) >"$LOG_DIR/$agent.prepare.log" 2>&1 &
  PIDS+=($!)
done

PREPARED=()
PREPARE_FAILED=()
for i in "${!AGENTS[@]}"; do
  agent="${AGENTS[$i]}"
  pid="${PIDS[$i]}"
  if wait "$pid"; then
    echo "OK   prepare: $agent"
    PREPARED+=("$agent")
  else
    echo "FAIL prepare: $agent (see $LOG_DIR/$agent.prepare.log)"
    PREPARE_FAILED+=("$agent")
  fi
done

if [[ ${#PREPARE_FAILED[@]} -gt 0 ]]; then
  for agent in "${PREPARE_FAILED[@]}"; do
    echo
    echo "── $agent prepare failure (last 20 lines) ──"
    tail -n 20 "$LOG_DIR/$agent.prepare.log"
  done
fi

if [[ ${#PREPARED[@]} -eq 0 ]]; then
  echo
  echo "No agent prepared successfully — nothing to deploy."
  exit 1
fi

# ── Phase 2: deploy each prepared agent in its own new Terminal window ─────────
if ! command -v osascript >/dev/null 2>&1; then
  echo "ERROR: osascript not found — spawning Terminal windows only works on macOS." >&2
  exit 1
fi

echo
echo "Opening ${#PREPARED[@]} Terminal window(s) — approve each one's confirmation prompt."

for agent in "${PREPARED[@]}"; do
  RUNNER="$LOG_DIR/$agent.deploy.sh"
  EXIT_FILE="$LOG_DIR/$agent.deploy.exit"
  cat > "$RUNNER" <<RUNEOF
#!/usr/bin/env bash
cd "$REPO_ROOT"
echo "=== Deploying $agent ==="
guava deploy up "$agent/deploy"
status=\$?
echo "\$status" > "$EXIT_FILE"
echo
if [[ "\$status" -eq 0 ]]; then
  echo "[$agent] deployed."
else
  echo "[$agent] FAILED (exit \$status)."
fi
RUNEOF
  chmod +x "$RUNNER"
  osascript -e "tell application \"Terminal\" to do script \"bash '$RUNNER'\"" >/dev/null
done

echo
echo "Waiting for all deploy windows to finish (approve each prompt to let it proceed)..."
WAITED=0
while true; do
  DONE_COUNT=0
  for agent in "${PREPARED[@]}"; do
    [[ -f "$LOG_DIR/$agent.deploy.exit" ]] && DONE_COUNT=$((DONE_COUNT + 1))
  done
  [[ "$DONE_COUNT" -eq "${#PREPARED[@]}" ]] && break
  sleep 2
  WAITED=$((WAITED + 2))
  if (( WAITED % 30 == 0 )); then
    echo "  still waiting on $((${#PREPARED[@]} - DONE_COUNT)) of ${#PREPARED[@]}..."
  fi
done

DEPLOY_FAILED=()
for agent in "${PREPARED[@]}"; do
  status="$(cat "$LOG_DIR/$agent.deploy.exit")"
  if [[ "$status" -ne 0 ]]; then
    DEPLOY_FAILED+=("$agent")
  fi
done

# ── Summary ──────────────────────────────────────────────────────────────────────
echo
echo "Prepare logs: $LOG_DIR"
echo
echo "Summary:"
for agent in "${AGENTS[@]}"; do
  if [[ " ${PREPARE_FAILED[*]-} " == *" $agent "* ]]; then
    echo "  $agent: FAILED (prepare)"
  elif [[ " ${DEPLOY_FAILED[*]-} " == *" $agent "* ]]; then
    echo "  $agent: FAILED (deploy)"
  else
    echo "  $agent: deployed"
  fi
done

if [[ ${#PREPARE_FAILED[@]} -gt 0 || ${#DEPLOY_FAILED[@]} -gt 0 ]]; then
  exit 1
fi
