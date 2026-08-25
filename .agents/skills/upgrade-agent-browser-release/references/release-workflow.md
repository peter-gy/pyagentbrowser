# Release workflow

Use this workflow for a requested official upstream release tag. Keep three
values distinct until the repository contract proves they should match:

- `UPSTREAM_TAG`: the official `agent-browser` tag to embed.
- `PACKAGE_VERSION`: the pyagentbrowser version to publish.
- `RELEASE_TAG`: the Git tag accepted by `scripts/release.sh`.
- `PUBLIC_VERIFY_PYTHON_VERSION`: one currently supported Python version from
  `pyproject.toml` and the live release matrix.

Set each value from the request and current version policy. Do not infer that
the package version must equal the upstream version.

## 1. Establish the live contract

Start from a clean, synchronized `main` checkout. Inspect the current command
and release surfaces before relying on history:

```bash
git status --short --branch
git fetch origin --prune
git rev-parse HEAD origin/main
git submodule status
git -C third_party/agent-browser remote -v
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef,url
```

Read the current Make targets, maintenance guide, version checks, package smoke
script, and both release workflows. Then compare several recent support and
release commits. Set `RECENT_SUPPORT_COMMIT` and `RECENT_RELEASE_COMMIT` to the
selected SHAs before inspecting them:

```bash
git log --all --decorate --graph --oneline -n 60
git log --all --oneline -- \
  third_party/agent-browser \
  src/agentbrowser/_upstream.json \
  crates/agent-browser-adapter/Cargo.toml \
  pyproject.toml
git show --stat "$RECENT_SUPPORT_COMMIT"
git show --stat "$RECENT_RELEASE_COMMIT"
```

History should answer two questions:

1. Which changes belong in the upstream-support layer?
2. Which current files move together for the SDK release version?

The support layer varies with upstream impact. The release layer is deliberately
small, but its current files still come from the live maintenance contract and
latest release diff.

## 2. Resolve the official target

Verify a requested tag through primary upstream records. For a request phrased
as "latest", compare the official latest release with the requested value.

```bash
gh api repos/vercel-labs/agent-browser/releases/latest \
  --jq '{tag_name,name,published_at,html_url}'
gh api 'repos/vercel-labs/agent-browser/tags?per_page=20' \
  --jq '.[] | [.name,.commit.sha] | @tsv'
git -C third_party/agent-browser ls-remote --tags origin \
  "refs/tags/$UPSTREAM_TAG" \
  "refs/tags/$UPSTREAM_TAG^{}"
```

Confirm that the release tag, planned package version, Git tag, and PyPI version
are unused. Published versions and tags cannot be replaced.

```bash
git tag -l "$RELEASE_TAG"
git ls-remote --tags origin \
  "refs/tags/$RELEASE_TAG" \
  "refs/tags/$RELEASE_TAG^{}"
curl --fail --silent --show-error \
  "https://pypi.org/pypi/pyagentbrowser/$PACKAGE_VERSION/json"
```

A successful PyPI response means the version already exists. A 404 means the
version is currently unused.

## 3. Create the support layer

The current release history favors a two-layer stack:

```text
main
  -> pgy/support-agent-browser-<upstream-version>
  -> pgy/release-pyagentbrowser-<package-version>
```

When `gh stack` is available, configure it for non-interactive use and create
the lower branch:

```bash
git config rerere.enabled true
git config remote.pushDefault origin
SUPPORT_BRANCH="pgy/support-agent-browser-${UPSTREAM_TAG#v}"
gh stack init --base main "$SUPPORT_BRANCH"
```

If the live repository no longer uses stacked PRs, preserve the same dependency
boundary with ordinary Git branches and PR bases.

## 4. Update and inspect upstream

Capture the old pin before running the canonical updater:

```bash
UPSTREAM_BEFORE=$(git rev-parse HEAD:third_party/agent-browser)
make update-upstream UPSTREAM_REF="$UPSTREAM_TAG"
UPSTREAM_AFTER=$(git -C third_party/agent-browser rev-parse HEAD)

git diff --submodule=log -- third_party/agent-browser
git -C third_party/agent-browser log --reverse --oneline \
  "$UPSTREAM_BEFORE..$UPSTREAM_AFTER"
git -C third_party/agent-browser diff --stat \
  "$UPSTREAM_BEFORE..$UPSTREAM_AFTER"
git -C third_party/agent-browser diff --name-status \
  "$UPSTREAM_BEFORE..$UPSTREAM_AFTER"
git -C third_party/agent-browser status --short
```

Inspect the full exact source diff. Classify each change before adapting it:

| Upstream change | Downstream decision |
| --- | --- |
| New crate-root or native Rust module | Add the selected module to the adapter only when generated code imports it. Add its direct dependencies and refresh `Cargo.lock`. |
| Changed source anchor | Update the exact fail-closed rewrite after reading the new source and confirming match cardinality. |
| New native action or field | Confirm raw execution first. Add typed Python support when the SDK owns stable semantics or an agent workflow. |
| Changed return or error data | Update strict decoding, typed errors, sync and async behavior, and consumer-facing tests together. |
| New `skill-data` content | Confirm native embedding and sdist inclusion. Add an artifact assertion when the file is required by build or runtime contracts. |
| Installer or system dependency | Update only the CI or user setup that exercises the supported path. |
| Platform, process, CDP, or browser lifecycle change | Add a real-browser or native integration test at that boundary. |
| Upstream docs, dashboard, JavaScript packages, or release automation | Record the review. Change pyagentbrowser only when its build, package, or public contract depends on it. |

Run `make test-native` early. A failure here often identifies a missing copied
module, missing direct dependency, or moved adapter anchor before broader tests
consume time.

If adapter manifest changes follow the canonical updater, refresh its lock entry:

```bash
cargo update --package agent-browser
```

## 5. Adapt the owned surfaces

Place changes by ownership:

- Adapter incompatibility: `crates/agent-browser-adapter`.
- PyO3 lifecycle or embedded resources: `crates/pyagentbrowser`.
- Stable Python workflow, validation, or result type: `src/agentbrowser`.
- Public contract: nearest SDK test plus sync and async parity.
- Browser or process behavior: integration test against real Chrome.
- Wheel or sdist input: `pyproject.toml`, package smoke, and clean-install proof.
- User-facing behavior: existing API reference and nearest runnable guide.

Keep upstream source clean. Do not patch files inside the submodule.

Cross-platform tests should exercise the same consumer boundary on each system:

- Use platform-native paths or a separator-free fixture when separators are not
  the contract.
- Defer platform-specific tools until the test enters the supported platform
  branch.
- Assert observable behavior instead of optional internal response fields.
- Use `browser.native.data()` when the test needs a raw mapping.
  `browser.native.execute()` returns a `BrowserResponse` envelope.
- Run Ty with `--python-platform all` when local platform specialization could
  hide another branch.

## 6. Validate efficiently

Use focused gates after each owned boundary changes:

```bash
make format
make test-sdk
make test-native
make rust-check rust-test
make test-package
make test-integration
```

Run only the gates relevant to each intermediate edit. Before packaging the
support commit, run the normal handoff gate plus every changed boundary:

```bash
make check
```

When platform-conditioned Python changed, add:

```bash
uv run --no-sync ty check --python-platform all
```

Use an available native Windows host for Windows-only path, process, or shell
failures. Reproduce at the exact commit, apply the narrow patch, rerun the
original command and the broader Windows marker set, then stop the host.

## 7. Package the support commit

Account for every hunk, stage exact paths, inspect `git diff --cached`, and let
commit hooks run. Use the recent repository convention for the title. A
capability-bearing update commonly uses:

```text
feat: support agent-browser <version>
```

A pure pin with no downstream capability work may use the established `chore:`
form. Keep the submodule pointer, adapter repair, public API, tests, docs,
package evidence, and required CI setup together when they depend on one
upstream release shape.

## 8. Create the release layer

Create the dependent branch after the support commit:

```bash
RELEASE_BRANCH="pgy/release-pyagentbrowser-$PACKAGE_VERSION"
gh stack add "$RELEASE_BRANCH"
```

Re-discover the synchronized release files from
`development_docs/maintenance.md`, `scripts/prepare_prerelease.py`, and the
latest release commit. Update them with structured edits, then refresh both
locks through their native tools. Verify the planned tag:

```bash
uv lock
cargo update --package pyagentbrowser
make prerelease-version-check
./scripts/release.sh check-version "$RELEASE_TAG"
```

Run the strongest local gate once at the final stack head:

```bash
CARGO_INCREMENTAL=0 make check-release
```

Package the version-only commit with the current release-title convention,
commonly:

```text
chore: prepare pyagentbrowser <version>
```

## 9. Submit and close CI

Submit the full stack non-interactively:

```bash
gh stack submit --auto --open --remote origin
gh stack view --json
```

Write short PR descriptions around the contract and review risk. Keep test
evidence in CI rather than pasting a mechanical command log into each body.

Use PR-attached checks as the source of truth:

Set `PR_NUMBER` to each PR returned by `gh stack view --json`, then run:

```bash
gh pr checks "$PR_NUMBER" --json name,bucket,state,workflow,link
gh pr checks "$PR_NUMBER" --watch --fail-fast
```

After a lower-layer fix:

```bash
gh stack rebase --upstack --no-trunk
gh stack push --remote origin
```

Confirm each active run uses the current branch SHA. A cancelled run from a
superseded base update is historical when a later exact-head run passed and the
PR reports `mergeStateStatus: CLEAN`.

Merge the current-head green stack through the stack command:

```bash
gh stack merge --yes --squash
```

## 10. Require exact-main evidence before tagging

Synchronize local `main` by fast-forward and capture its SHA:

```bash
git fetch origin --prune
git switch main
git merge --ff-only origin/main
RELEASE_SHA=$(git rev-parse HEAD)
```

Find the push-event `Release Check` whose `headSha` equals `RELEASE_SHA`. Watch
it to a successful aggregate `Required gate`. PR evidence cannot replace this
step because the publish workflow queries successful push evidence for the tag
commit.

Confirm the tag is unused, then create and push it at `RELEASE_SHA`:

```bash
git tag -a "$RELEASE_TAG" -m "pyagentbrowser $PACKAGE_VERSION"
git push origin "$RELEASE_TAG"
```

## 11. Follow publishing through public verification

Resolve the tag-triggered `Publish` run and require every job:

- release commit and tag evidence
- current platform wheel builds and source distribution
- architecture-specific wheel tests
- artifact validation and trusted PyPI publishing
- GitHub release notes
- public installs on the configured operating systems
- final PyPI artifact and GitHub release verification

Inspect the live workflow for the current platform and artifact set. Use
`scripts.package_smoke.expected_release_artifact_names()` for the expected PyPI
filenames instead of copying a past release's set.

Perform an independent clean install from public PyPI in a new temporary
environment. Use an exact version, PyPI's public index, and no cache. Verify:

- distribution and import versions
- `agentbrowser.__agent_browser_version__`
- `_version.UPSTREAM_COMMIT`
- `Browser().session.status()` before launch
- `browser.native.data("stream_status")`
- terminal `close()` behavior
- package dependency consistency

Respect the machine supply-chain policy. When the user explicitly requested
verification of a newly published version and the exact artifact already passed
CI and metadata checks, the permitted one-command uv exception is:

```bash
PUBLIC_VERIFY_DIR=$(mktemp -d /tmp/pyagentbrowser-public.XXXXXX)
trap '/usr/bin/trash "$PUBLIC_VERIFY_DIR"' EXIT
uv venv --python "$PUBLIC_VERIFY_PYTHON_VERSION" "$PUBLIC_VERIFY_DIR/venv"
uv pip install --python "$PUBLIC_VERIFY_DIR/venv/bin/python" \
  --exclude-newer 2100-01-01 \
  --no-cache \
  --index-url https://pypi.org/simple \
  "pyagentbrowser==$PACKAGE_VERSION"
uv pip check --python "$PUBLIC_VERIFY_DIR/venv/bin/python"
```

Leave the global age gate unchanged.

Verify PyPI JSON for the exact version, file hashes, yanked state, and artifact
set. A browser may receive PyPI's client challenge on the human project page.
Use the public JSON endpoint and do not bypass the challenge.

## 12. Audit completion

Before reporting success, inspect current state for every required outcome:

```bash
git status --short --branch
git rev-parse HEAD origin/main "$RELEASE_TAG^{}"
git cat-file -t "$RELEASE_TAG"
git submodule status
gh release view "$RELEASE_TAG" \
  --json tagName,isDraft,isPrerelease,publishedAt,url
```

Also verify merged PR SHAs, current-head PR runs, exact-main release run,
Publish run, public PyPI metadata, clean install output, and temporary resource
cleanup. Report concrete links and SHAs.
