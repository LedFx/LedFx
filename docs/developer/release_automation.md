# Release publication and Discord recovery

Release-please owns the version update, changelog, tag, and draft release. CI
builds and smoke-tests the tag, then one production approval promotes the
tested artifacts. The publication job uploads verified archives to the draft,
publishes Python distributions and versioned Docker manifests, verifies signed
provenance, and makes GitHub public last. `release: published` starts a separate
Discord workflow; notification failures cannot rerun publication.

## Credentials and approvals

`ledfx-automation` needs repository **Contents: read/write** to publish the
draft and persist delivery checkpoints, and **Attestations: read/write** to
store and verify release provenance. Its existing PR/issue permissions remain
used by release-please and PR-title automation, but publication tokens request
only contents and attestations. Notification tokens request only contents.

The complete App configuration for these workflows is:

| Repository permission | Access | Used for |
| --- | --- | --- |
| Contents | Read/write | Release-please tags/drafts, final publication, delivery state |
| Attestations | Read/write | Store and verify artifact provenance |
| Pull requests | Read/write | Release-please release PRs and existing PR automation |
| Issues | Read/write | Release-please labels and existing PR comments |
| Metadata | Read (automatic) | Repository metadata |

Install the App only on repositories it operates on. No organization permission
or additional Actions, Workflows, Administration, or Artifact metadata permission
is required for this release flow. The publication job separately grants its
workflow token `id-token: write` and `packages: write` for signing and GHCR.

Keep `AUTOMATION_APP_CLIENT_ID` and `AUTOMATION_APP_PRIVATE_KEY` available to
both the production publication job and the independent notification workflow.
The notification workflow also needs repository secrets
`DISCORD_ANNOUNCEMENTS_WEBHOOK`, `DISCORD_RELEASETHREAD_WEBHOOK`, and
`SHAUNS_OPENROUTER_KEY`. A forum/media channel webhook is required for release
threads. Set repository variable `OPENROUTER_MODEL` to override
`openrouter/auto`.

Use webhooks from the same Discord server: announcements link to the thread
using Discord's clickable channel reference (`<#thread-id>`).

PyPI still uses Trusted Publishing. GHCR uses the workflow's packages-write
token; Docker Hub uses its existing credentials. Official provenance signing
uses the job's OIDC token. OCI attestations are pushed to the registries with
optional storage records disabled, so `artifact-metadata: write` is not needed.
No new production approval is added for notification retries.

## Publication and retries

The publisher requires the release-please draft, a remote tag resolving to the
tested commit, nonempty release notes, the four expected frozen archives, and
a matching wheel/sdist. It never creates a replacement tag or guesses release
notes. Missing draft assets are uploaded. Existing GitHub and PyPI files must
match the local SHA-256 checksums; a conflicting file stops publication without
deletion or replacement. Versioned Docker manifests must reference the same
tested AMD64 and ARM64 digests. Authentication and network failures are not
treated as missing releases, files, or manifests.

Rerun failed publication jobs from the **same tag run**, preserving the tested
artifacts. Once GitHub is public, retries verify the release and its provenance
without changing assets, release notes, or latest pointers. If a retry finds a
different payload under an existing version, investigate rather than moving
the tag or clobbering a published file.

Publication jobs queue across tags. A stable `vMAJOR.MINOR.PATCH` version moves
GitHub latest and Docker latest only when no newer stable GitHub release has
already been published. An older maintenance version still gets its versioned
downloads and Docker tags. Prereleases never become the stable latest.

Maintenance patches are eligible too: publishing `v2.2.1` after `v2.2.0` updates
both Docker latest tags and GitHub latest when it is the newest stable release.
If `v2.3.0` is already public, publishing `v2.2.1` preserves those latest pointers.
Newer drafts and prereleases do not prevent a stable patch from becoming latest.

GitHub, PyPI, and the registries do not provide a shared transaction. A failed
run can leave verified assets staged or a distribution already published;
rerunning the same tag resumes by checking what exists. Published GitHub versions
determine stable ordering: if a newer draft fails after promoting Docker latest,
a subsequent older draft can move Docker latest until the newer GitHub release
is public. The publisher rechecks release identity before writes and publishes
by release ID, but GitHub's release API provides no atomic metadata
compare-and-swap, and the registries provide no
portable create-if-absent guard. Avoid editing the draft, moving the tag, or
running another publisher for these Docker tags while publication is running.

## Verify provenance

The production CI job generates signed provenance for the four frozen
archives, the wheel/sdist, and both registries' promoted image indexes. PyPI's
PEP 740 attestations remain enabled as well. The GitHub draft is published only
after provenance verification checks the repository, CI signer workflow,
source tag and commit, and GitHub-hosted runner identity.

Stable Docker latest tags move only after those checks pass. Each latest tag
copies the exact attested image-index digest; GitHub publication follows last.

For a downloaded file, substitute the tag and commit of the release:

```bash
gh attestation verify LedFx-2.2.1-win-x64.zip \
  --repo LedFx/LedFx \
  --signer-workflow LedFx/LedFx/.github/workflows/ci.yml \
  --source-ref refs/tags/v2.2.1 \
  --source-digest RELEASE_COMMIT_SHA \
  --deny-self-hosted-runners
```

For an image, use its immutable digest rather than a mutable latest tag:

```bash
gh attestation verify oci://ghcr.io/ledfx/ledfx@sha256:IMAGE_DIGEST \
  --repo LedFx/LedFx \
  --signer-workflow LedFx/LedFx/.github/workflows/ci.yml \
  --source-ref refs/tags/v2.2.1 \
  --source-digest RELEASE_COMMIT_SHA \
  --deny-self-hosted-runners
```

These attestations establish which workflow promoted these bytes from the
release's source commit. They do not establish reproducibility or independently
audit the source or dependencies. See [GitHub's attestation guide](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
and the [verification command](https://cli.github.com/manual/gh_attestation_verify).

## Notification delivery

The notification workflow fetches the published release and executes scripts
from the default branch. It first posts the full changelog to a version-titled
thread, splitting long notes without truncation. Whitespace-only fragments use
code fences so Discord accepts them while preserving the original characters.
It then asks OpenRouter for
short highlights and posts the summary with release and thread links. An LLM
failure produces a factual fallback; it does not prevent full changelog
delivery. Messages cannot ping users or roles.

Delivery checkpoints live on branch `automation/release-notifications`, in
`releases/<GitHub-release-id>.json`. The branch is created automatically from
the default branch when needed. Ensure branch protection/rules permit the
automation App to write that operational branch. It does not trigger main/tag
CI or release-please. State contains IDs, changelog hashes, generated message
content and progress; webhook URLs and credentials are never recorded.

The sender saves a pending operation **before** sending and confirmed IDs
**after** Discord acknowledges it. Confirmed chunks/messages are skipped on
retry. A definite rejected request can be retried; a timeout, lost confirmation,
or checkpoint error stops automatic delivery because the message may already
exist. The workflow reports this uncertainty instead of replaying a send.

Retry notifications independently from the default branch:

```bash
gh workflow run release-notifications.yml --repo LedFx/LedFx --ref main \
  -f tag=v2.2.1
```

For an unresolved pending operation, inspect Discord and the release's state
file on the operational branch. State schema version 1 records confirmed
changelog messages in `message_ids`; its length determines the next chunk.
Use Discord's developer mode to copy the message and thread/channel IDs.

- If `pending.kind` is `chunk` and that chunk was delivered, append its message
  ID to `message_ids`. For `pending.index == 0`, also set `thread_id` to the
  created thread's channel ID. Set `pending` to JSON `null`.
- If `pending.kind` is `announcement` and it was delivered, set
  `announcement.id` to the message ID and set `pending` to `null`.
- If the pending message is verified absent, set only `pending` to `null`;
  preserve confirmed progress so the next dispatch sends that operation.

Then dispatch again. Keep `schema_version`, release identity, `source_sha256`,
`chunk_sha256`, and the persisted announcement content/hash intact. Edit only
the pending operation's confirmation fields; do not remove required keys or
delete the entire state file. Deleting state discards confirmed delivery
evidence and permits duplicates. Uncertain delivery requires operator
reconciliation rather than an exactly-once guarantee across Discord and GitHub.

Dry runs display the proposed content without sending or writing state. They
can still incur an OpenRouter request when a key is configured. Development
tests mock the external services; do not use the real webhooks for validation.

## Maintenance branches

Backport the publication scripts and notification workflow before the next
maintenance tag. GitHub loads a release-event workflow from the released tag;
checking out notification code from the default branch does not install the
workflow into an old tag. Default-branch manual dispatch can announce an older
published release once this workflow is installed on main.

Follow [Releasing a patch](releasing_a_patch.md) for compatibility checks and
release-please setup. Keep its patch-only versioning configuration confined to
the maintenance branch.
