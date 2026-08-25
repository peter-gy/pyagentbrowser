---
name: upgrade-agent-browser-release
description: Upgrade pyagentbrowser to an official agent-browser release and carry the change through adapter repair, SDK alignment, stacked PRs, exact-SHA CI, tagging, PyPI publishing, and public verification. Use for end-to-end upstream release bumps in this repository, not generic SDK changes.
---

# Upgrade agent-browser and release pyagentbrowser

Move one official upstream release through the complete pyagentbrowser release
state machine. Treat the live repository and official upstream tag as the source
of truth. Previous releases show the pattern, while current code defines the
contract.

## Start from current evidence

Before changing the pin:

1. Read `AGENTS.md`, `development_docs/architecture.md`, and
   `development_docs/maintenance.md` completely.
2. Read the narrow instructions for every owned source or test area the change
   may touch.
3. Read [the release workflow](references/release-workflow.md) completely.
4. Inspect the clean worktree, current branch, remotes, submodule status,
   current versions, recent upstream-support commits, recent release commits,
   merged PRs, releases, and active workflows.
5. Resolve the requested upstream tag through the official upstream release and
   tag records. When the user asks for the latest release, verify that claim
   before selecting the tag.

Do not reuse a previous release's file list, API work, test count, runner
matrix, or artifact names without checking the current tree.

## Authorization boundary

Read-only discovery is always allowed. Pushes, PR creation, merges, tags, and
publication require authorization in the current request. A request that
explicitly asks to upgrade, push, merge, publish, and verify the release
authorizes that full sequence.

Once a full release is authorized, continue through public artifact
verification. Green local tests, open PRs, green PR checks, a merge, or a tag are
intermediate states.

## Durable contracts

- Keep `third_party/agent-browser` as immutable pinned input. Use
  `make update-upstream UPSTREAM_REF=<tag>` to move it.
- Generate adaptations in `OUT_DIR`. Keep adapter rewrites narrow, exact, and
  fail-closed.
- Preserve `browser.native.execute(action, **params)` and
  `browser.native.data(action, **params)` as complete raw boundaries.
- Add a typed Python surface when pyagentbrowser owns stable validation,
  lifecycle, evidence, result decoding, or an agent workflow. Keep uncommon or
  volatile native commands on the raw boundary.
- Keep synchronous and asynchronous public behavior aligned.
- Keep support behavior, its tests, contract docs, adapter inputs, package
  evidence, and required CI setup in one coherent support layer.
- Keep SDK release metadata in a dependent release layer whose file set is
  rediscovered from current maintenance docs and recent release commits.
- Require current-head PR checks for every layer, then a successful push-event
  `Release Check` for the exact merged `main` SHA before tagging.
- Treat published artifacts as immutable. If publication begins and a later
  gate fails, fix forward with a new version and tag.

## State machine

```text
official upstream tag
  -> support layer
  -> release metadata layer
  -> current-head PR checks
  -> stack merge
  -> exact-main Release Check
  -> annotated tag
  -> Publish workflow
  -> clean public install and metadata verification
```

Use focused gates while adapting upstream code. Run the cold full release gate
at the final stack head. Let the PR workflows provide independent full-matrix
evidence for both layers.

## Failure handling

- Reproduce a failure at its owning boundary before editing.
- Inspect the exact new upstream source before changing an adapter anchor or
  adding a copied module or dependency.
- When a lower stack layer changes, rebase every upper layer and push the stack
  through the stack tool.
- Treat superseded cancelled CI runs as history. Prove the active run's
  `headSha`, required gate, and PR merge state.
- For a platform-only failure, validate on that platform when a native host is
  available. Stop any temporary host after collecting evidence.
- Stop for missing external authorization, missing authentication, a dirty
  submodule, an unexpected upstream remote, an existing release tag or PyPI
  version, or a non-fast-forward target that the user did not request.

## Completion evidence

The release is complete when current evidence proves all of these:

- `main`, `origin/main`, and the annotated release tag resolve to the same
  commit.
- The pinned submodule and `_upstream.json` resolve to the official upstream
  tag and commit.
- Support and release PRs are merged from green current-head suites.
- The exact-main `Release Check` and tag-triggered `Publish` workflow succeeded.
- The GitHub release is public with the correct prerelease state.
- PyPI exposes the exact expected artifact set and no file is yanked.
- A no-cache install from public PyPI passes package version, embedded engine
  version, provenance, native lifecycle, `stream_status`, and dependency checks.
- The worktree is clean and temporary browser sessions or native hosts are
  closed.
