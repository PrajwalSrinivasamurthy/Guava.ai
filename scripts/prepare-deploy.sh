#!/usr/bin/env bash
# Build a deploy-ready copy of a Guava project under <project>/deploy/.
#
# Idempotent: wipes and regenerates everything except the deployment-identity
# file, which must persist across runs so `guava deploy up` recognizes the
# deployment. `guava update` renamed that file .guava → guava.toml, so both
# names are preserved — whichever the project has. On a first build (deploy/
# has no identity file yet), it's seeded from the project root's guava.toml /
# .guava instead of being left empty — otherwise `guava deploy up` finds no
# config, offers to initialize a NEW project, and orphans the real deployment.
#
# Usage:
#   ./scripts/prepare-deploy.sh                          # uses current directory
#   ./scripts/prepare-deploy.sh path/to/project          # explicit project dir
#
# Behavior:
#   - If the project has config_sheet.py + .env, runs it first
#     (`uv run --env-file .env python config_sheet.py`) to refresh
#     config_cache.json from the live sheet — non-fatal on failure, deploys
#     with the last successfully cached config instead.
#   - Copies all *.py files from project root, renaming __main__.py → main.py
#   - Detects `[tool.uv.sources]` entries with `path = ...`, vendors each
#     pattern as sibling source in deploy/, and rewrites pyproject.toml to
#     (a) drop the path-dep line, (b) replace the dep name in [dependencies]
#     with the pattern's own declared deps (inlined from the pattern's own
#     pyproject.toml). No hardcoded pattern knowledge — new patterns are
#     picked up automatically.
#   - Copies known optional secrets/data files if present:
#       .env  credentials.json  token.pickle  token.pickle.issued_at
#       config_cache.json
#   - Preserves guava.toml / .guava across rebuilds (restored immediately after
#     mkdir so a mid-script failure can't orphan the deployment identity).
#   - Regenerates uv.lock in deploy/ so the cloud build uses `uv sync --frozen`.
#   - Cleans any __pycache__ and .venv that leaked in from local testing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PATTERNS_DIR="$REPO_ROOT/patterns"

if [[ $# -gt 0 ]]; then
  PROJECT_DIR="$(cd "$1" && pwd)"
else
  PROJECT_DIR="$(pwd)"
fi

if [[ ! -f "$PROJECT_DIR/pyproject.toml" ]]; then
  echo "ERROR: no pyproject.toml at $PROJECT_DIR — not a Python project?" >&2
  exit 1
fi

cd "$PROJECT_DIR"

# ── Refresh cached sheet-sourced config, if this project has the pattern ────
# Projects built on the config_sheet.py + patterns/gsheets convention cache
# sheet-sourced data (FAQ content, shared phone-number config, ...) in
# config_cache.json so the deployed agent never needs live sheet access at
# runtime. Refresh it here so every deploy ships current data — this is what
# makes cached numbers/content "update every deploy" rather than going stale.
# Non-fatal: a refresh failure warns but doesn't block the deploy, since the
# project already falls back to its last successfully cached config_cache.json
# (or its hardcoded defaults, for values never cached at all).
if [[ -f config_sheet.py && -f .env ]]; then
  echo "Refreshing config_cache.json from the live sheet..."
  if ! uv run --env-file .env python config_sheet.py; then
    echo "WARNING: config_sheet.py refresh failed — deploying with the existing" >&2
    echo "         cached config_cache.json (if any) instead of fresh sheet data." >&2
  fi
fi

DEPLOY_DIR="deploy"

# ── Preserve the deployment-identity file across rebuilds ────────────────────
# `guava update` renamed .guava → guava.toml. Stash whichever the project has
# (under its own name) so `guava deploy up` still recognizes the deployment.
IDENTITY_NAME=""
IDENTITY_CONTENT=""
IDENTITY_SOURCE=""
for _id in guava.toml .guava; do
  if [[ -f "$DEPLOY_DIR/$_id" ]]; then
    IDENTITY_NAME="$_id"
    IDENTITY_CONTENT="$(cat "$DEPLOY_DIR/$_id")"
    IDENTITY_SOURCE="deploy"
    break
  fi
done

# ── First-time seed: deploy/ has no identity yet — pull it from the project ─
# root's guava.toml / .guava instead of leaving deploy/ with none. Without
# this, `guava deploy up` sees no config at all and offers to initialize a
# NEW project — minting a new project_id and orphaning any already-live
# deployment (see gotchas/deploy-auth.md).
if [[ -z "$IDENTITY_NAME" ]]; then
  for _id in guava.toml .guava; do
    if [[ -f "$PROJECT_DIR/$_id" ]]; then
      IDENTITY_NAME="$_id"
      IDENTITY_CONTENT="$(cat "$PROJECT_DIR/$_id")"
      IDENTITY_SOURCE="root"
      break
    fi
  done
fi

if [[ -z "$IDENTITY_NAME" ]]; then
  echo "WARNING: no guava.toml/.guava in deploy/ or at the project root — deploy/" >&2
  echo "         will have no deployment identity. Fine for a genuinely new" >&2
  echo "         project (guava deploy up will offer to initialize one); if this" >&2
  echo "         project has ever deployed before, stop and locate its guava.toml." >&2
elif [[ "$IDENTITY_SOURCE" == "root" ]]; then
  echo "Seeding deploy/$IDENTITY_NAME from the project root's $IDENTITY_NAME."
fi

rm -rf "$DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR"

# ── Restore it immediately so downstream failures can't orphan it ────────────
if [[ -n "$IDENTITY_NAME" ]]; then
  printf '%s\n' "$IDENTITY_CONTENT" > "$DEPLOY_DIR/$IDENTITY_NAME"
fi

# ── Copy *.py files; rename __main__.py → main.py ────────────────────────────
shopt -s nullglob
for f in *.py; do
  if [[ "$f" == "__main__.py" ]]; then
    cp "$f" "$DEPLOY_DIR/main.py"
  else
    cp "$f" "$DEPLOY_DIR/"
  fi
done
shopt -u nullglob

# ── Vendor path-sourced patterns + rewrite pyproject.toml ───────────────────
# The inline Python helper parses pyproject.toml, finds every
# `<name> = { path = "..." }` entry under [tool.uv.sources], vendors each
# pattern, and produces a stripped pyproject.toml with the pattern's deps
# inlined. It also prints the vendored pattern names (one per line) to
# fd 3 so the shell can act on them.
VENDORED=$(python3 - "$PROJECT_DIR/pyproject.toml" "$DEPLOY_DIR/pyproject.toml" "$PATTERNS_DIR" <<'PY'
import os
import re
import sys
import tomllib

src_path, dst_path, patterns_dir = sys.argv[1], sys.argv[2], sys.argv[3]

with open(src_path) as f:
    lines = f.readlines()

# Find vendored patterns: entries under [tool.uv.sources] with path = ...
vendored: dict[str, str] = {}  # name → absolute pattern dir
in_sources = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith("[tool.uv.sources]"):
        in_sources = True
        continue
    if stripped.startswith("[") and in_sources:
        in_sources = False
    if in_sources:
        m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_-]*)\s*=\s*\{[^}]*\bpath\s*=\s*"([^"]+)"', line)
        if m:
            name, relpath = m.group(1), m.group(2)
            abs_src = os.path.normpath(os.path.join(os.path.dirname(src_path), relpath))
            if not os.path.isdir(abs_src):
                print(f"WARNING: path dep {name!r} → {abs_src!r} missing — skipping", file=sys.stderr)
                continue
            vendored[name] = abs_src

# Load pattern deps for each vendored pattern
pattern_deps: dict[str, list[str]] = {}
for name, src in vendored.items():
    with open(os.path.join(src, "pyproject.toml"), "rb") as f:
        data = tomllib.load(f)
    pattern_deps[name] = data.get("project", {}).get("dependencies", [])

# Rewrite lines
out: list[str] = []
seen_deps: set[str] = set()  # dedup within [dependencies]
for line in lines:
    # Drop '<name> = { path = ... }' lines entirely
    drop = False
    for name in vendored:
        if re.match(rf'^{re.escape(name)}\s*=\s*\{{[^}}]*\bpath\s*=', line):
            drop = True
            break
    if drop:
        continue

    # Replace '"<name>",' in dependencies with pattern's declared deps
    replaced = False
    for name, deps in pattern_deps.items():
        m = re.match(rf'^(\s*)"{re.escape(name)}"\s*,?\s*$', line)
        if m:
            indent = m.group(1)
            for dep in deps:
                key = re.split(r'[=<>!~\s]', dep, maxsplit=1)[0].lower()
                if key in seen_deps:
                    continue
                seen_deps.add(key)
                out.append(f'{indent}"{dep}",\n')
            replaced = True
            break
    if replaced:
        continue

    # For existing dep lines, skip if we already inlined the same dep from a
    # pattern; otherwise mark it as seen for later pattern-inlines to dedup.
    dep_match = re.match(r'^\s*"([^"]+)"\s*,?\s*$', line)
    if dep_match:
        key = re.split(r'[=<>!~\s]', dep_match.group(1), maxsplit=1)[0].lower()
        if key in seen_deps:
            continue
        seen_deps.add(key)

    out.append(line)

with open(dst_path, "w") as f:
    f.writelines(out)

# Print vendored pattern names + their source dirs so the shell can use the
# actual path-dep target. The pattern's Python import name comes from the
# basename of that path (underscored, e.g. `string_utils`), which can differ
# from the PEP-503-normalized dep name (hyphenated, e.g. `string-utils`).
for name, abs_src in vendored.items():
    package_name = os.path.basename(abs_src)
    print(f"{package_name}\t{abs_src}")
PY
)

# Copy each vendored pattern's source folder as sibling in deploy/. The
# package_name is what Python imports (underscored); the source path is the
# actual pattern dir under patterns/.
while IFS=$'\t' read -r package_name abs_src; do
  [[ -z "$package_name" ]] && continue
  PATTERN_SRC="$abs_src/$package_name"
  if [[ ! -d "$PATTERN_SRC" ]]; then
    echo "ERROR: vendored pattern source missing: $PATTERN_SRC" >&2
    exit 1
  fi
  cp -r "$PATTERN_SRC" "$DEPLOY_DIR/$package_name"
  rm -rf "$DEPLOY_DIR/$package_name/__pycache__"
  echo "Vendored: $package_name"
done <<< "$VENDORED"

# ── Runtime secrets & data (optional — only copy if present) ────────────────
# WARNING: this overwrites deploy/.env with the project-root .env on EVERY regen.
# Any secret that lives ONLY in deploy/.env (and not in the root .env) is silently
# wiped each time this runs. Keep such secrets in the root .env (or set them on the
# Guava platform); otherwise you must re-add them to deploy/.env after each regen.
# (Hit concretely on KCI: GUAVA_OPENAI_KEY lived only in deploy/.env and got stripped
#  on every run, re-breaking the cloud OpenAI-proxy path.)
for f in .env credentials.json token.pickle token.pickle.issued_at config_cache.json; do
  if [[ -f "$f" ]]; then
    cp "$f" "$DEPLOY_DIR/"
  fi
done

# ── Comment out platform-injected keys in the deploy .env ───────────────────
# GUAVA_API_KEY is reserved — Guava Deploy rejects a bundle that sets it
# (422 "env key 'GUAVA_API_KEY' is reserved", see gotchas/deploy-auth.md).
# GUAVA_AGENT_NUMBER is injected from guava.toml's phone_number at deploy time.
# Comment both out so the bundle doesn't fight the platform.
if [[ -f "$DEPLOY_DIR/.env" ]]; then
  for key in GUAVA_API_KEY GUAVA_AGENT_NUMBER; do
    sed -i '' -E "s|^[[:space:]]*((export[[:space:]]+)?${key}[[:space:]]*=.*)\$|# \\1  # (deploy: platform-injected)|" "$DEPLOY_DIR/.env"
  done
fi

# ── Runtime markdown assets (e.g. pet_policy.md for DocumentQA) ─────────────
# Copy any *.md at the project root that isn't a known internal doc. This
# catches runtime knowledge files (FAQs, policies) that get read at startup,
# without shipping the dev-facing README / spec / PROVENANCE.
shopt -s nullglob
for f in *.md; do
  case "$f" in
    README.md|spec.md|PROVENANCE.md|NOTES.md|TODO.md) continue ;;
  esac
  cp "$f" "$DEPLOY_DIR/"
  echo "Bundled markdown asset: $f"
done
shopt -u nullglob

# ── Generate a fresh uv.lock for the deploy package ─────────────────────────
# Shipping uv.lock tells the cloud builder to run `uv sync --frozen`, giving
# reproducible builds rather than re-resolving each deploy.
(cd "$DEPLOY_DIR" && uv lock --quiet)

# ── Drop any local-test artifacts ───────────────────────────────────────────
find "$DEPLOY_DIR" -name __pycache__ -type d -exec rm -rf {} +
rm -rf "$DEPLOY_DIR/.venv"

echo
echo "deploy/ rebuilt at $(date -Is)"
echo
echo "Contents of $PROJECT_DIR/$DEPLOY_DIR/:"
ls -la "$DEPLOY_DIR"
