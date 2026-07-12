---
name: ship-aihsm
description: Use when cutting or publishing a new aihsm release while in the dtsoden/aihsm repo. Triggers on "ship aihsm", "release aihsm", "publish aihsm", "cut a release", "bump version", "push out a new aihsm build", or any request to get a new aihsm version onto PyPI and the plugin marketplace.
---

# Ship aihsm

aihsm ships through two channels at once, and each reads its version from a different file.
A release is only correct when both move together, plus a matching git tag. Skip one and a
`pip install` user and a `/plugin install` user end up on different builds of the same number.

- **PyPI** (`pip install aihsm`) reads `version` from `pyproject.toml`.
- **Plugin marketplace** (`/plugin install aihsm@aihsm`) reads `version` from `.claude-plugin/plugin.json`.

PyPI is immutable: you can never re-upload a version that already exists. Every release bumps
the number.

## Preconditions

- Current directory is the aihsm repo (git remote `dtsoden/aihsm`).
- `gh auth status` shows the active account is `dtsoden`.
- The PyPI API token is in the OS vault under the name `pypi` (check with `aihsm list`). If it
  is missing, run `aihsm put pypi` before starting; never paste the token into the terminal.
- Python 3 is on PATH. `python -m build --version` and `python -m twine --version` both work;
  if not, `python -m pip install --upgrade build twine`.

## Release steps

1. **Pick the new version** `X.Y.Z` (semver). It must be greater than the current one, or the
   PyPI upload will be rejected.

2. **Bump both files to the same value:**
   - `pyproject.toml` -> `version = "X.Y.Z"`
   - `.claude-plugin/plugin.json` -> `"version": "X.Y.Z"`

3. **Build clean.** The repo leaves a local `build/` directory behind, and its mere presence
   makes `python -m build` fail with `No module named build` (the folder shadows the build
   tool). Always wipe it first:
   ```bash
   rm -rf build dist
   python -m build
   ```

4. **Validate before publishing:**
   ```bash
   python -m twine check dist/*
   claude plugin validate .
   ```

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

7. **Verify the new version is live:**
   ```bash
   python -m pip index versions aihsm   # should list X.Y.Z as latest
   ```
   Plugin users pick it up the next time they update the marketplace and plugin from the
   `/plugin` menu. PyPI users get it with `pip install --upgrade aihsm`.

8. **Clean up** the `build/` and `dist/` directories (both gitignored) so the next release
   starts from a clean tree.

## Common mistakes

| Mistake | Result | Fix |
| --- | --- | --- |
| Bumped `pyproject.toml`, forgot `plugin.json` | pip users and plugin users diverge | Always edit both in step 2 |
| Reused an existing version number | `twine upload` 400s ("File already exists") | Bump higher; you cannot overwrite a PyPI version |
| Ran `python -m build` with a stale `build/` present | `No module named build` | `rm -rf build dist` first (step 3) |
| Pasted the PyPI token to upload | Token in transcript, now burned | Use `aihsm run --set TWINE_PASSWORD=pypi` (step 5) |
| Forgot to push the tag | GitHub release history has no `vX.Y.Z` | `git push origin vX.Y.Z` |
