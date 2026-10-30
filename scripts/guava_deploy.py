#!/usr/bin/env python3
"""Deploy a prepared bundle to Guava using an API key (no `guava` CLI).

The CLI only authenticates via interactive OAuth, so it can't run in CI. The
deploy API accepts a plain API key as a Bearer token, so this talks to it
directly. The endpoints are undocumented; the flow below was captured from
`guava deploy up` (CLI 0.46.0) through a logging proxy on 2026-10-02, so it can
break when the CLI/API changes.

Usage:
  scripts/guava_deploy.py status <project_dir> [--wait]    # read-only: is it running?
  scripts/guava_deploy.py bundle <project_dir> [out.zip]   # zip deploy/, print sha256
  scripts/guava_deploy.py up     <project_dir> [--dry-run] # update the live deployment

<project_dir> is e.g. inbound-k12; its deploy/ (built by prepare-deploy.sh)
and deploy/guava.toml are used. `up` only UPDATES an existing deployment; the
first deploy of a project must still be done once with `guava deploy up`.

Env: GUAVA_DEPLOY_API_KEY (an API key for the org that owns the project),
     GUAVA_BASE_URL (default https://app.goguava.ai/).

Do NOT send an x-guava-org-id header: with an API key the API answers 401
"Malformed bearer auth". The org is implied by the key.

Flow of `up` (all under /push2prod/v1):
  1. POST deploy/prepare  {project_id, call_direction, bundle_hash, base_image, force_rebuild}
        -> {cache_hit, cloud_build_id, build_status, upload_url, has_active_deployment}
  2. if not cache_hit: PUT <upload_url> (application/zip), then
     POST build {project_id, base_image, bundle_hash} -> {result, build_id, cloud_build_id}
  3. poll GET build/<cloud_build_id> until status SUCCESS
  4. PATCH deployment {project_id, project_name, guava_agent_number, resource_cpu,
        resource_memory, spot, replicas, call_direction, env, enable_healthcheck}
        -> {result: "ok", task_id, build_id}   (POST here creates a NEW task: don't)
  5. poll GET project/<id>/status until running with ready_replicas == replicas
"""

import hashlib
import json
import os
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BASE_URL = os.environ.get("GUAVA_BASE_URL", "https://app.goguava.ai/").rstrip("/")

# guava.toml's `tier` -> (resource_cpu, resource_memory), the same table the
# CLI (0.49.0) uses to fill these fields. An unknown tier is refused rather than
# guessed, since sending the wrong resources silently resizes the deployment.
TIERS = {
    "guava-seed": ("1", "1Gi"),
    "guava-fruit": ("2", "2Gi"),
    "guava-tree": ("4", "4Gi"),
}
BUILD_FAILED = {"FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"}


def api(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    key = os.environ.get("GUAVA_DEPLOY_API_KEY")
    if not key:
        sys.exit("GUAVA_DEPLOY_API_KEY is not set")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE_URL}/push2prod/v1/{path.lstrip('/')}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or "null")
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def must(method: str, path: str, body: dict | None = None) -> dict:
    code, payload = api(method, path, body)
    if code != 200 or not isinstance(payload, dict):
        sys.exit(f"{method} {path} failed: HTTP {code} {json.dumps(payload)[:300]}")
    return payload


def load_identity(project_dir: Path) -> dict:
    toml_path = project_dir / "deploy" / "guava.toml"
    if not toml_path.exists():
        # Without the identity file a deploy would mint a NEW project and orphan
        # the live one (see scripts/prepare-deploy.sh).
        sys.exit(f"missing {toml_path} — refusing to deploy without the project identity")
    return tomllib.loads(toml_path.read_text())


def parse_env(path: Path) -> dict[str, str]:
    """Parse deploy/.env the way the CLI forwards it as the deployment's env."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def make_bundle(project_dir: Path, out: Path) -> str:
    """Zip deploy/ deterministically and return the sha256 of the zip.

    The server's own bundle_hash algorithm is unknown (it differs from this
    for identical code); it accepts ours as an opaque cache key.
    """
    root = project_dir / "deploy"
    fixed = (1980, 1, 1, 0, 0, 0)  # constant timestamps -> reproducible zip
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(str(path.relative_to(root)), fixed)
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def deployment_body(project_dir: Path, identity: dict) -> dict:
    tier = identity.get("tier")
    if tier not in TIERS:
        sys.exit(f"unknown or missing tier {tier!r} in deploy/guava.toml (expected one of {', '.join(TIERS)})")
    cpu, memory = TIERS[tier]
    body = {
        "project_id": identity["project_id"],
        "project_name": identity["name"],
        "resource_cpu": cpu,
        "resource_memory": memory,
        "spot": False,
        "replicas": identity.get("replicas", 1),
        "call_direction": identity["call_direction"],
        "env": parse_env(project_dir / "deploy" / ".env"),
        "enable_healthcheck": identity.get("enable_healthcheck", True),
    }
    if "phone_number" in identity:
        body["guava_agent_number"] = identity["phone_number"]
    return body


def cmd_status(project_dir: Path, *flags: str) -> int:
    """With --wait, polls up to 5 min for "running" (a rollout shows "pending"
    for a minute or so); without it, checks once."""
    pid = load_identity(project_dir)["project_id"]
    deadline = time.time() + (300 if "--wait" in flags else 0)
    while True:
        code, body = api("GET", f"project/{pid}/status")
        print(code, json.dumps(body), flush=True)
        state = None
        if code == 200 and isinstance(body, dict) and isinstance(body.get("status"), dict):
            state = body["status"].get("state")
        if state == "running":
            return 0
        if time.time() >= deadline:
            return 1
        time.sleep(10)


def cmd_bundle(project_dir: Path, out: Path | None = None) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        dest = out or Path(tmp) / "bundle.zip"
        digest = make_bundle(project_dir, dest)
        print(f"{dest.stat().st_size} bytes sha256 {digest}" + (f" -> {dest}" if out else ""))
    return 0


def upload(url: str, data: bytes) -> None:
    req = urllib.request.Request(url, data=data, method="PUT", headers={"Content-Type": "application/zip"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            if resp.status != 200:
                sys.exit(f"bundle upload failed: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        sys.exit(f"bundle upload failed: HTTP {e.code}")


def wait_for_build(cloud_build_id: str, timeout: int = 1200) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = must("GET", f"build/{cloud_build_id}").get("status")
        print(f"  build {status}", flush=True)
        if status == "SUCCESS":
            return
        if status in BUILD_FAILED:
            sys.exit(f"build {cloud_build_id} ended with {status}")
        time.sleep(15)
    sys.exit(f"build {cloud_build_id} did not finish within {timeout}s")


def wait_for_running(project_id: str, replicas: int, task_id: str | None = None, timeout: int = 600) -> None:
    """Waits for THIS rollout: until the status reports our task_id, the old
    deployment's "running" would pass the check before the new one starts."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = must("GET", f"project/{project_id}/status")
        status = body["status"]
        print(f"  deployment {status['state']} ({status.get('ready_replicas')}/{status.get('replicas')}) task {body.get('task_id')}", flush=True)
        if (
            (task_id is None or body.get("task_id") == task_id)
            and status["state"] == "running"
            and status.get("ready_replicas") == status.get("replicas") == replicas
        ):
            return
        time.sleep(10)
    sys.exit(f"deployment not running with {replicas} ready replicas within {timeout}s")


def cmd_up(project_dir: Path, *flags: str) -> int:
    dry_run = "--dry-run" in flags
    identity = load_identity(project_dir)
    body = deployment_body(project_dir, identity)

    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "bundle.zip"
        digest = make_bundle(project_dir, bundle)
        print(f"bundle {bundle.stat().st_size} bytes sha256 {digest[:16]}…")

        if dry_run:
            shown = {**body, "env": {k: "<hidden>" for k in body["env"]}}
            print("dry run — no requests sent. PATCH deployment body would be:")
            print(json.dumps(shown, indent=2))
            return 0

        prep = must("POST", "deploy/prepare", {
            "project_id": identity["project_id"],
            "call_direction": identity["call_direction"],
            "bundle_hash": digest,
            "base_image": identity["base_image"],
            "force_rebuild": False,
        })
        if not prep["has_active_deployment"]:
            sys.exit("no active deployment for this project: run `guava deploy up` once to create it")

        if prep["cache_hit"]:
            print("no changes: reusing existing build")
            cloud_build_id = prep["cloud_build_id"]
        else:
            print("uploading bundle")
            upload(prep["upload_url"], bundle.read_bytes())
            built = must("POST", "build", {
                "project_id": identity["project_id"],
                "base_image": identity["base_image"],
                "bundle_hash": digest,
            })
            cloud_build_id = built["cloud_build_id"]
        wait_for_build(cloud_build_id)

    print("updating deployment")
    result = must("PATCH", "deployment", body)
    if result.get("result") != "ok":
        sys.exit(f"deployment update failed: {json.dumps(result)[:300]}")
    wait_for_running(identity["project_id"], body["replicas"], result.get("task_id"))
    print(f"deployed: task {result['task_id']} build {result['build_id']}")
    return 0


COMMANDS = {"status": cmd_status, "bundle": cmd_bundle, "up": cmd_up}

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    cmd, project, rest = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
    sys.exit(COMMANDS[cmd](project, *(Path(a) for a in rest) if cmd == "bundle" else rest))
