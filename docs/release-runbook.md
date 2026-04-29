# ai-crawler release runbook

This runbook covers the maintained npm wrapper release flow for `@cafitac/ai-crawler`.

## Preconditions

- work from a clean branch based on `main`
- `gh` is authenticated as `cafitac`
- `NPM_TOKEN` is configured in GitHub repo secrets
- local checks pass before tagging

## Version files

Keep these versions identical before any release:

- `package.json`
- `pyproject.toml`
- `src/ai_crawler/__init__.py`

The publish workflow now enforces this consistency and will fail early if they drift.

## Pre-release local verification

Run these before pushing a release tag:

```bash
bash scripts/check-python.sh
bash scripts/verify-ai-harness.sh
npm test
npm pack --dry-run
```

Optional explicit guard smoke:

```bash
uv run --extra dev python -m ai_crawler.release.npm_publish --event-name workflow_dispatch --ref-name main
```

## Tag-triggered release flow

1. update the version in all release files
2. commit the version bump on a branch and merge it to `main`
3. fast-forward local `main`
4. create a tag matching `npm-v<version>`
5. push the tag

Example for `0.1.1`:

```bash
git checkout main
git pull --ff-only origin main
git tag npm-v0.1.1
git push origin npm-v0.1.1
```

The workflow validates that the pushed ref exactly matches `npm-v<package.json version>` before publishing.

## Manual workflow_dispatch release

If the tag push path did not run, trigger `.github/workflows/npm-publish.yml` with `workflow_dispatch` on `main`.

This path still validates version consistency, but it does not require a tag.

## Post-publish validation

Treat publish completion and published-install smoke as separate gates.

Check registry visibility:

```bash
npm view @cafitac/ai-crawler version name dist-tags --json
```

Then verify the real published artifact from outside the repo:

```bash
tmpdir=$(mktemp -d)
cd "$tmpdir"
npm exec --yes --package @cafitac/ai-crawler@0.1.1 ai-crawler -- --version
npm exec --yes --package @cafitac/ai-crawler@0.1.1 ai-crawler -- doctor
npm exec --yes --package @cafitac/ai-crawler@0.1.1 ai-crawler -- mcp-config --client hermes --launcher npm
npm install @cafitac/ai-crawler@0.1.1
./node_modules/.bin/ai-crawler --version
./node_modules/.bin/ai-crawler doctor
```

For MCP onboarding smoke, also verify the published wrapper can emit npm-first client config:

```bash
npm exec --yes --package @cafitac/ai-crawler@0.1.1 ai-crawler -- mcp-config --client hermes --launcher npm
```

## Failure triage

If publish fails:

- version mismatch: fix `package.json`, `pyproject.toml`, or `src/ai_crawler/__init__.py`
- bad tag: push the correct `npm-v<version>` tag
- auth failure: verify repo secret `NPM_TOKEN`
- registry propagation delay: wait and retry published-install smoke before changing code

If published-install smoke fails but publish succeeded:

- inspect wrapper delegation in `lib/wrapper.cjs`
- confirm tarball metadata includes `lib/wrapper-metadata.json` during pack/publish
- verify delegated Python spec resolution outside the repo
