# Releasing a patch

A patch release ships selected fixes from the last stable release while main continues toward the next feature release. This guide uses 2.2.1 as an example: start from `v2.2.0`, retain its config format and v1 API, and backport compatible fixes. Publish the maintenance commit through the existing tag-based CI workflow.

## Select and backport fixes

Fetch the remote branches and tags before choosing the release base:

```bash
git fetch origin --prune --tags
git log --reverse --oneline v2.2.0..origin/main
git diff --stat v2.2.0..origin/main
git worktree add -b release/2.2.1 /tmp/ledfx-release-2.2.1 v2.2.0
cd /tmp/ledfx-release-2.2.1
```

Review each candidate with `git show <commit>` and record the selected and excluded changes in the release PR. Backport with `git cherry-pick -x <commit>` to preserve provenance. Include the fix's regression tests. If a fix uses main's newer configuration models or shared managers, adapt it to the stable release's interfaces or defer it. Do not bring an entire refactor into a patch just to make a cherry-pick apply.

For 2.2.1, Sendspin requires both #1970 (`8040be73`, client API and identity lifecycle) and #2063 (`7818f114`, unpaired access before connection). The Windows installer fix is #2020 (`0bad7372`), including its install, upgrade over a running process, and uninstall smoke tests. The new config migration, API v2, and removal of v1 routes are excluded.

## Configure release please for the maintenance branch

The maintenance copy of `.github/workflows/release-please.yml` accepts pushes to `release/2.2`, passes `target-branch: ${{ github.ref_name }}`, and uses a concurrency group containing the branch ref. This keeps main's release PR independent of the patch release PR. The workflow also restricts manual runs to the configured release branches.

The maintenance branch's `release-please-config.json` uses `"versioning": "always-bump-patch"`. Release-please provides this strategy specifically for backport branches. Review compatibility before backporting: a patch-only version strategy does not make a breaking change safe. Keep main's default version strategy on main. The root manifest on the maintenance branch initially records `2.2.0`.

Retain `draft: true`, `force-tag-creation: true`, and the GitHub App token. Release-please must create the tag immediately even while the release is a draft, and the App token lets the generated PR and tag trigger CI. Events created with the default `GITHUB_TOKEN` do not trigger another workflow. See the [official multiple-branch setup](https://github.com/googleapis/release-please-action#supporting-multiple-release-branches) and [patch strategy](https://github.com/googleapis/release-please/blob/main/src/versioning-strategies/always-bump-patch.ts).

## Prepare the frontend and release notes

Leave backend version files at the last released version in the backport PR. Release-please will bump all four locations in its release PR:

| File | Field |
| --- | --- |
| `pyproject.toml` | `project.version` |
| `ledfx/consts.py` | `PROJECT_VERSION` |
| `uv.lock` | Version of the `ledfx` package only |
| `.release-please-manifest.json` | Root package version |

Prepare a summary of the selected fixes and compatibility scope for reviewing the generated changelog. Keep dependency pins unchanged unless a selected fix requires a dependency update, then check with `uv lock --check`.

The bundled frontend reports its own version. Release-please does not rewrite the minified bundle or rename its assets. A backend-only version bump leaves the header and update notification showing the previous release. Before merging the release PR, relabel the existing UI using the same approach as 2.2.0:

```bash
python3 tools/bump_frontend_version.py 2.2.0 2.2.1
```

The helper changes the one frontend version export, gives the main JavaScript bundle a new filename derived from its executable content, renames its license file, and updates `index.html`, `asset-manifest.json`, and `service-worker.js`. It also refreshes the service worker's index revision. New filenames matter for returning browsers and cached Workbox clients: the bundled `service-worker.js` lists the main bundle with `revision: null`, so changing bytes under the old URL can leave cached clients on old code. The current HTML registers the separate lightweight `serviceWorker.js`, which does not precache assets; keep both the HTML references and the bundled Workbox manifest consistent.

Inspect the diff and confirm that the old bundle name has no remaining references and every manifest entry points to a real file. Load the UI in a browser, check the header version, and exercise an upgrade with an existing service worker. If the helper cannot identify the version export or precache entry, inspect the changed bundle format before proceeding. This relabeling is for shipping an unchanged bundled UI; rebuild from frontend source when UI behavior changes.

## Validate the maintenance branch

Run the stable line's tests and hooks:

```bash
uv sync --frozen --python 3.12 --group dev
uv run --frozen prek run --all-files
uv run --frozen pytest -v --timeout=120
git diff --check
```

Create the maintenance base once, then open the patch PR against it. For the first 2.2 patch, the base is `v2.2.0`; subsequent patches start from the current maintenance branch:

```bash
git branch release/2.2 v2.2.0
git push origin release/2.2
git push -u origin release/2.2.1
gh pr create --base release/2.2 --head release/2.2.1 \
  --title 'fix: release 2.2.1 maintenance fixes' --body-file /tmp/release-pr.txt
```

Wait for the hosted test matrix, frozen builds, package and Docker builds, and smoke tests to pass before merging. CI covers Python 3.11 through 3.14, Windows, both macOS architectures, and both Docker architectures. For a maintenance branch without an open PR, explicitly run validation:

```bash
gh workflow run ci.yml --ref release/2.2
```

CI already runs on PRs and manual dispatches. Adding maintenance branches to `push.branches` is not necessary for this process. If you add automatic branch builds later, also restrict Docker's `PUBLISH` expression to main and release tags; its current push condition assumes those are the only push triggers.

## Merge the release please PR

After merging the backport PR, the push to `release/2.2` runs release-please and opens its own release PR targeting that branch. If needed, trigger it explicitly:

```bash
gh workflow run release-please.yml --ref release/2.2
gh pr list --base release/2.2
```

Inspect the generated PR: the version must be 2.2.1 in every backend file, the changelog must describe only the selected backports, and the frontend must already report 2.2.1. Keep release-please's PR labels and release metadata intact. Wait for the release PR's hosted CI to pass, then merge it into `release/2.2`.

The next release-please run recognizes its merged PR and creates `v2.2.1` and a draft GitHub release with the changelog. Let it create these; do not manually bump the manifest, create a competing tag, or publish the draft before CI finishes.

## Publish the tested artifacts

The `v*` tag push triggers `ci.yml` even when the tagged commit is on a maintenance branch. The Plan job requires the tag to match `pyproject.toml` exactly. The production environment currently allows tags matching `v*` and requires a configured reviewer; no maintenance branch permission is needed. GitHub documents [branch and tag trigger filters](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushbranchestagsbranches-ignoretags-ignore) and [environment deployment policies](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).

Wait for `CI passed` on the tag run, inspect the artifact and smoke-test results, then approve its production deployment. The verified publication job promotes the artifacts from that run to PyPI and Docker, verifies signed provenance, and publishes the GitHub draft last. Sentry remains independent telemetry. Tag builds do not move Docker's `edge` tags. A patch such as `v2.2.1` updates both Docker `latest` tags and GitHub latest when it is the newest stable release; if a newer stable version such as `v2.3.0` has a draft or public GitHub release, it preserves those pointers. An abandoned newer stable draft can delay latest promotion until a maintainer resolves it, while versioned publication remains available. Check that publication finishes successfully.

Before tagging, backport the reviewed shared action pin, publication workflow wiring, `.github/release-policy.json`, and `release-notifications.yml` workflow to the maintenance branch. Published events load workflow definitions from the released tag, while notification code itself runs from the default branch. See [Release publication and Discord recovery](release_automation.md) for App permissions, attestation verification, notification retries, and recovery after uncertain delivery.

For the next patch, backport fixes from main to `release/2.2` and repeat this process. Release-please advances the maintenance manifest and opens the next patch PR. Main continues generating its own feature-release PR. Keep the frontend helper and release instructions available on main as well, but do not carry the maintenance branch's patch-only version strategy into main.

## Verify the published release

Confirm the GitHub release is public and has four frozen archives: Windows portable, Windows installer, macOS ARM64, and macOS Intel. Check PyPI's version and both registries' versioned Docker manifests, including AMD64 and ARM64. Open the packaged UI and verify that it reports the patch version. For 2.2.1, confirm `/api/v2` is absent and the existing v1 API still works.

If a job fails, fix or rerun the failed jobs before claiming the release is complete. Retry publishing from the same tag run so it uses the tested artifacts. Published versions and release tags are permanent identifiers; do not move a tag to different code to retry a release.
