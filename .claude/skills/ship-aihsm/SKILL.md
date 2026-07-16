---
name: ship-aihsm
description: Use when cutting or publishing a new aihsm release while in the dtsoden/aihsm repo. Triggers on "ship aihsm", "release aihsm", "publish aihsm", "cut a release", "bump version", "push out a new aihsm build", or any request to get a new aihsm version onto PyPI and the plugin marketplace.
---

# Ship aihsm

aihsm ships through two channels at once, and each reads its version from a different file.
A release is only correct when both move together, plus a matching git tag. Skip one and a
`pip install` user and a `/plugin install` user end up on different builds of the same number.

- **PyPI** (`pip install aihsm`) reads `version` from `pyproject.toml`.
- **Self-hosted plugin marketplace** (`/plugin marketplace add dtsoden/aihsm` then
  `/plugin install aihsm@aihsm`) reads `version` from `.claude-plugin/plugin.json`. This is live
  now; anyone can add it straight from the repo with no approval.

PyPI is immutable: you can never re-upload a version that already exists. Every release bumps
the number.

The **official Anthropic plugin directory** is a separate, third thing and is currently **on
hold**: the submission account is pending approval (as of 2026-07-12). Its scaffolding already
exists (`.claude-plugin/marketplace.json` and `plugin.json`), so nothing needs building. This
release pipeline is deliberately blind to that approval. It ships to PyPI and the self-hosted
marketplace every time and never waits on the official directory. Submitting there is a one-off
manual step (see "Official directory" below), not part of cutting a release.

## Preconditions

- Current directory is the aihsm repo (git remote `dtsoden/aihsm`).
- `gh auth status` shows the active account is `dtsoden`.
- The PyPI API token is in the OS vault under the name `pypi` (check with `aihsm list`). If it
  is missing, run `aihsm put pypi` before starting; never paste the token into the terminal.
- Python 3 is on PATH. `python -m build --version` and `python -m twine --version` both work;
  if not, `python -m pip install --upgrade build twine`.
- Claude Code is up to date, so `claude plugin validate` checks against Anthropic's current
  manifest schema. The plugin manifest format changes over time under you; the validator is how
  you catch it, so a stale CLI defeats the whole guard.

## Release steps

1. **Pick the new version** `X.Y.Z` (semver). It must be greater than the current one, or the
   PyPI upload will be rejected.

2. **Bump both files to the same value:**
   - `pyproject.toml` -> `version = "X.Y.Z"`
   - `.claude-plugin/plugin.json` -> `"version": "X.Y.Z"`

   Those are the only two. `aihsm.__version__` derives from installed package metadata, so it
   follows `pyproject.toml` on its own. Never hardcode it back into `aihsm/__init__.py`: it used
   to be a constant and silently drifted, still reporting 0.1.0 after 0.1.1 shipped. A test
   (`test_version_is_not_hardcoded_and_matches_package_metadata`) fails if anyone re-introduces it.

3. **Build clean.** The repo leaves a local `build/` directory behind, and its mere presence
   makes `python -m build` fail with `No module named build` (the folder shadows the build
   tool). Always wipe it first:
   ```bash
   rm -rf build dist
   python -m build
   ```

4. **Validate before publishing (hard gate).** Both commands must pass. Do not publish if either
   fails.
   ```bash
   python -m twine check dist/*
   claude plugin validate .
   ```
   `claude plugin validate` checks `.claude-plugin/plugin.json` and `marketplace.json` against the
   schema the installed Claude Code knows about. Anthropic changes that schema over time (new
   required fields, renamed keys, stricter path rules). If the validator errors, or warns about an
   unknown, missing, renamed, or deprecated field, STOP. Do not wave it through. Open the current
   spec at https://code.claude.com/docs/en/plugin-marketplaces, compare the two manifest files
   against the official examples in `anthropics/claude-plugins-official` and `anthropics/claude-code`,
   edit them to match, and re-run until it passes clean. Never publish a manifest the current CLI
   rejects: a bad manifest breaks `/plugin install` for everyone and gets an official-directory
   submission bounced.

5. **Publish to PyPI** with the token pulled from the vault and masked out of the output:
   ```bash
   export TWINE_USERNAME=__token__
   aihsm run --set TWINE_PASSWORD=pypi -- python -m twine upload --non-interactive dist/*
   ```

6. **Commit, tag, push** (keep the message clean; no AI attribution):
   ```bash
   git commit -am "release: vX.Y.Z"
   git tag vX.Y.Z
   git push origin main
   git push origin vX.Y.Z
   ```

7. **Create the GitHub release** so the repo's Releases page matches PyPI (`gh` active account
   must be `dtsoden`). Write short notes covering what changed:
   ```bash
   gh release create vX.Y.Z --title "aihsm X.Y.Z" --notes "..."
   ```

8. **Verify the new version is live:**
   ```bash
   python -m pip index versions aihsm   # should list X.Y.Z as latest
   ```
   Plugin users pick it up the next time they update the marketplace and plugin from the
   `/plugin` menu. PyPI users get it with `pip install --upgrade aihsm`.

9. **Clean up** the `build/` and `dist/` directories (both gitignored) so the next release
   starts from a clean tree.

## Official directory (on hold)

Submitting aihsm to Anthropic's official/community plugin directory is a separate, manual, one-time
step, not part of cutting a release. It is currently blocked on account approval (pending as of
2026-07-12). When the account is live:

1. Confirm `claude plugin validate .` passes clean (step 4 already does this every release).
2. Submit through the current Anthropic plugin submission flow. Confirm the URL in the docs first;
   it has moved before. Approval pins the plugin to a commit SHA in
   `anthropics/claude-plugins-community`.

Until then, do nothing here. The self-hosted marketplace already lets anyone install, so the
release pipeline never waits on this.

## Common mistakes

| Mistake | Result | Fix |
| --- | --- | --- |
| Bumped `pyproject.toml`, forgot `plugin.json` | pip users and plugin users diverge | Always edit both in step 2 |
| Reused an existing version number | `twine upload` 400s ("File already exists") | Bump higher; you cannot overwrite a PyPI version |
| Ran `python -m build` with a stale `build/` present | `No module named build` | `rm -rf build dist` first (step 3) |
| Pasted the PyPI token to upload | Token in transcript, now burned | Use `aihsm run --set TWINE_PASSWORD=pypi` (step 5) |
| Forgot to push the tag | GitHub has no `vX.Y.Z` tag | `git push origin vX.Y.Z` |
| Published to PyPI but skipped `gh release create` | GitHub Releases page lags behind PyPI | Run step 7 every release |
| Published a manifest the current CLI rejects | `/plugin install` breaks; official submission bounced | Treat `claude plugin validate` as a hard gate (step 4); fix against the current spec |
| Held a release waiting on official-directory approval | pip and plugin users get nothing | The pipeline is blind to that approval; ship anyway |
