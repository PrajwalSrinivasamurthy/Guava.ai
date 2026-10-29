# Texas Tech × Guava

Shared repository for voice agents Guava builds with and for Texas Tech.

## Local development

```
cd inbound-k12
cp .env.example .env        # fill in the secrets
uv run pytest -v            # offline tests (live tier is skipped unless RUN_LIVE=1)
```

`./run_all_tests.sh --offline` runs every agent's offline suite.

## Versions and rollback

`guava deploy` has no versions or rollback (latest bundle wins), so versions live in git:

- Every successful deploy from `main` is tagged `deploy/<agent>/<YYYYMMDD-HHMM>-<sha7>`.
- The commit is also written to `<agent>/deploy/VERSION` inside the bundle.
- List versions: `git tag -l 'deploy/inbound-k12/*' | sort`
- Roll back (rebuilds and redeploys that tag's code; tests are skipped unless you pass `-f run_tests=true`):

  ```
  gh workflow run deploy.yml -f agent=inbound-k12 -f ref=deploy/inbound-k12/<tag>
  ```

A rollback restores **code, `settings.py` and dependency versions** (the bundle is locked from that commit's `uv.lock`). The deploy tooling (`prepare-deploy.sh`, `guava_deploy.py`) always comes from `main`, so any commit can be redeployed, not just tagged ones. It does **not** restore secrets: GitHub secrets are not versioned, so a rotated secret stays rotated.

## Pipeline

- `checks.yml` ("Checks"): offline `pytest` for every agent against its committed `uv.lock` (`--locked`, so a stale lock fails), plus a check that each deployed agent's `deploy/guava.toml` is tracked (losing it would orphan the live deployment). Runs on pull requests and pushes to `main`.
- `deploy.yml`: one generic workflow for every whitelisted agent. A `plan` job reads `.github/deploy-agents.json` (from main's copy, never from the deployed `ref`) and picks the agents to deploy: on push, each enabled agent whose directory changed (a change under `patterns/` or `scripts/` redeploys all enabled agents); on manual dispatch, the `agent` you name, which must be enabled. Each agent then deploys in its own matrix job: tests (if `"tests": true`), write the secrets into `.env`, `scripts/prepare-deploy.sh`, `scripts/guava_deploy.py up`, a status check, then the tag. Deploys of one agent never overlap; different agents can run in parallel. Every job is guarded with `github.ref == 'refs/heads/main'`: dispatching the workflow from any other branch does nothing and can't read the secrets.
- **FAQ / shared-number cache:** CI has no Google credentials, so a CI deploy ships the committed `config_cache.json` as-is. Refresh it locally (`uv run --env-file .env python config_sheet.py`) and commit it to change what a deploy ships.
- **Adding an agent:** it needs a tracked `<agent>/deploy/guava.toml` and one prior manual `guava deploy up`. Add an entry to `.github/deploy-agents.json` (`enabled`, `tests`, and `secrets` as `{"<name in the agent's .env>": "<repository secret name>"}`), add those repository secrets, and merge. Merging the entry alone deploys nothing (only a change in the agent's own directory, `patterns/` or `scripts/` does), so dispatch its first CI deploy by hand: `gh workflow run deploy.yml -f agent=<agent>`. Setting `"enabled": false` stops it deploying without removing the entry. `GUAVA_API_KEY` is always written into the bundle as `GUAVA_LOCAL_API_KEY`.
- `scripts/guava_deploy.py` deploys with an API key because the `guava` CLI only supports interactive login. The manual deploy below is the fallback.
- **Not live yet:** the deploy workflow is off until the repo variable `DEPLOY_ENABLED` is `true`.
- `up` only **updates** an existing deployment. The first deploy of a new project needs `guava deploy up` once.
- **Scaling comes from git, not the dashboard:** every deploy sets replicas to `replicas` in the agent's `deploy/guava.toml` (1 if absent) and resources to 1 CPU / 1Gi. A replica count or resource change made in the Guava dashboard is reset by the next deploy of that agent (and a `patterns/` or `scripts/` change redeploys all of them). To scale, edit `replicas` in `deploy/guava.toml` and commit it.

## Required GitHub setup

Under Settings → Secrets and variables → Actions:

| Item | Kind | Notes |
|---|---|---|
| `GUAVA_API_KEY` | repository secret | One Guava API key for the org that owns the agents. The deploy workflow uses it to deploy, and also writes it into the bundle as `GUAVA_LOCAL_API_KEY`. Shared across agents. |
| `DEPLOY_ENABLED` | repository **variable** | Set to `true` to turn the deploy workflow on. |

No agent needs other secrets today: every other runtime value is a default in its `settings.py`, so change those there, not in `.env`. If an agent gains a secret, map it in `.github/deploy-agents.json`; the deploy fails early with `repository secret X is not set` if a mapped secret is missing. Because the same key is also the agents' runtime key, rotate it everywhere at once. Secrets are repo-wide, so keep the workflow's `main`-only guard and restrict who can push to `main` (branch protection).

## Trying the deploy script locally

```
export GUAVA_DEPLOY_API_KEY=...        # same key as the GUAVA_API_KEY secret
./scripts/prepare-deploy.sh inbound-k12
python3 scripts/guava_deploy.py up inbound-k12 --dry-run   # prints the request body, sends nothing
python3 scripts/guava_deploy.py status inbound-k12         # read-only
python3 scripts/guava_deploy.py up inbound-k12             # real deploy: restarts the live agent
```

## Manual deploy (fallback)

```
./scripts/prepare-deploy.sh inbound-k12
cd inbound-k12/deploy && guava deploy up
```

`./scripts/deploy-all.sh` does this for every agent at once (macOS).
