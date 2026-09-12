# Embedded resources

pyagentbrowser compiles selected upstream source and data into its native
extension and source distribution. These resources remain traceable to the
exact upstream pin.

## Resource inventory

| Resource                             | Build owner                | Installed purpose                               |
| ------------------------------------ | -------------------------- | ----------------------------------------------- |
| Upstream Rust modules                | Adapter build script       | Native browser engine                           |
| Browser and JavaScript protocol JSON | Adapter build script       | Generated CDP Rust types                        |
| `skill-data` tree                    | PyO3 build script          | Agent-facing skill files exposed through Python |
| pyagentbrowser Agent Plugin          | Python build backend       | Marimo code-mode discovery and Python guidance  |
| Upstream version and commit          | Update and release scripts | Runtime provenance                              |
| Upstream and axe-core notices        | Packaging manifest         | License compliance                              |

The source distribution includes the source form of every build input. A wheel
contains the resulting extension, provenance record, and license material.

## Skill-data pipeline

`crates/pyagentbrowser/build.rs` walks the pinned upstream `skill-data` tree,
sorts normalized relative paths, normalizes line endings, and writes one JSON
payload into Cargo `OUT_DIR`. The native extension exposes that payload through
`skill_data_json()`.

`src/agentbrowser/skills.py` parses the payload lazily and exposes skill names,
frontmatter descriptions, main `SKILL.md` content, supplementary parts, and a
combined Markdown view. It validates that each directory name matches the
skill's frontmatter name.

The pinned upstream files are the content source. Python owns the stable read
API and its validation. A skill-data change therefore requires upstream-diff
review, native embedding proof, Python API proof, and package proof.

## Agent Plugin pipeline

The root `plugin.json` and `skills/pyagentbrowser/` tree provide Python-specific
instructions for Python code-mode agents. `_agent_plugins_maturin.py` wraps the
Maturin Python build backend so editable installs, wheels, and source
distributions carry the Agent Plugin marker and exact resource inventory.

The cross-platform wheel workflow invokes Maturin directly inside platform
builders, then runs `agent-plugins attach-wheel` before artifact validation.
Direct and PEP 517 wheel builds use the same `agent_plugins.attach_wheel()`
implementation. Package smoke tests verify the marker, payload, wheel record,
staged source resources, and normalized source-distribution timestamps.

## Protocol-generation inputs

The adapter reads pinned browser and JavaScript protocol schemas and generates
Rust types in `OUT_DIR`. Those types support the embedded engine and are
different from the optional Python direct CDP client, which sends dynamic
method names and mappings.

Treat a schema update as an upstream source change. Compile the adapter and run
the browser seams that use affected engine behavior.

## Provenance

`src/agentbrowser/_upstream.json` records the upstream version and commit. The
Python version module exposes both values. Packaging tests compare this record
with the live submodule commit and the upstream Cargo manifest.

Do not derive provenance from a branch name. Branches move. The gitlink commit
is the embedded source identity.

## Change checklist

1. Inspect the resource diff at the old and new upstream commits.
2. Update the upstream pin and generated assumptions together.
3. Keep build output in Cargo `OUT_DIR`.
4. Include every required source input in the source distribution.
5. Update project and third-party notices when license inputs change.
6. Run `make test-native`, `make test-package`, and `make package`.

[Packaging](packaging.md) defines final artifact contents. [Maintenance](maintenance.md)
defines upstream intake and release ordering.
