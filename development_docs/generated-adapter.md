# Generated adapter

`crates/agent-browser-build` registers selected modules from the
pinned upstream submodule, writes adapted modules and wrapper trees to Cargo
[`OUT_DIR`](https://doc.rust-lang.org/cargo/reference/build-scripts.html#outputs-of-the-build-script),
and generates protocol types. The adapter's build script calls this crate.
Cargo compiles the resulting modules inside `agent-browser-adapter`.

The upstream checkout is immutable input. Every downstream rewrite has a narrow inspected anchor, an expected match count, and a failure path when upstream moves.

The adapter compiles upstream executable code as an embedded library. It
assigns process ownership, threads downstream identity through upstream state,
and exposes the operations consumed by PyO3. Upstream owns generic browser
behavior.

## Inputs and outputs

| Kind                         | Location                                      |
| ---------------------------- | --------------------------------------------- |
| Pinned source modules        | `third_party/agent-browser/cli/src/`          |
| Pinned source resources      | Files included by registered source modules   |
| Pinned protocol schemas      | `third_party/agent-browser/cli/cdp-protocol/` |
| Downstream dependency mirror | `crates/agent-browser-adapter/Cargo.toml`     |
| Module registry and protocol generation | `crates/agent-browser-build/src/registry.rs` and `src/protocol/` |
| Capability transformations | `crates/agent-browser-build/src/features/` |
| Runtime document behavior | `crates/agent-browser-adapter/src/documents/` |
| Engine settings, confirmation, and namespace | `crates/agent-browser-adapter/src/options.rs`, `confirmation.rs`, and `namespace.rs` |
| Generated Rust modules       | Cargo `OUT_DIR`                               |
| Stable library exports       | `crates/agent-browser-adapter/src/lib.rs`     |

The adapter exports `Engine` and owned configuration and resource operations.
Generated upstream manager types stay inside that crate. PyO3 consumes the
owned interface, so a change to upstream state types stops at the adapter
boundary.

Generated Rust stays outside version control. The source distribution carries
the pinned inputs and transformation program, so a local build runs without a
Git submodule checkout.

## Generated surfaces

| Surface               | Downstream contract                                                                  | Nearest evidence                            |
| --------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------- |
| Upstream module tree  | Register engine modules and write adapted modules needed by the embedded library     | Adapter Rust smoke and native smoke         |
| CDP protocol types    | Generate browser and JavaScript protocol bindings from upstream JSON schemas         | Adapter compilation and native engine seams |
| Confirmation identity | Park each command under its request ID. Authorize `confirm` against that ID, the current policy, and allowed domains before upstream replays the command. Authorize `deny` against that ID | Adapter smoke confirmation cases            |
| Locator policy action | Check a semantic locator command under the action it performs as well as its own name | Adapter smoke policy cases and the semantic-query confirmation seam |
| Session settings      | Build the settings from environment defaults, the environment connection target, and engine options, keep security settings in process memory, and refuse a planned change to them except a first allowed-domains list | Adapter smoke and native option tests       |
| Chrome launch flags   | Enable the WebMCP feature under the name Chrome 157 and later use                    | WebMCP browser seam                         |
| Engine namespace      | Send upstream's reads of the process namespace to the namespace the calling thread entered, so the socket and state directories follow each engine | Adapter smoke, native namespace, and namespace integration tests |
| Tab binding           | Expose stable `targetId`                                                             | Tab and integration tests                   |
| Stream response       | Preserve the success envelope expected by Python                                     | Native stream tests                         |
| Dashboard boundary    | Expose stream observation while Python retains browser control and session ownership | Native dashboard tests                      |

## Change workflow

1. Inspect the exact old and new upstream source range.
2. Identify which registered file or rewrite anchor changed.
3. Decide whether the downstream invariant still belongs in the adapter.
4. Update the smallest rewrite and its expected match count.
5. Keep generated output in `OUT_DIR`.
6. Run `make test-native` for rewrite and [PyO3](https://pyo3.rs/) Rust-to-Python boundary evidence.
7. Run `make rust-check rust-test` for Rust ownership.
8. Run the Python or browser boundary test affected by the adapted behavior.

An anchor failure means the pinned source needs a re-audit. Broadening a text match until the build passes can rewrite the wrong construct.

## Fail-closed transformations

Each replacement records its feature, source module, patch name, expected match
count, and dependencies on earlier patches. Missing or duplicate anchors stop
generation. A replacement that overlaps generated text must name the earlier
patches it depends on. Unused dependency declarations also fail.

`agent_browser_build::generate(source_root, output_dir)` returns the input and
patch report. Failures preserve the partial report with the failed source
contract. The adapter build script uses the inputs to register Cargo rebuild
dependencies. Generation checks source assumptions. Compilation and runtime
tests check the resulting behavior.

Inspect the generated module when debugging, then change the transformation or
its source registry. Never repair build output directly. Change a match count
only after you read the new upstream structure and state the intended
cardinality.

## Adding registered modules

Upstream modules referenced by registered source must also appear in the adapter
module tree. Non-Rust files included by those modules must be registered as
source inputs. Update the module and resource registry, source-distribution
inclusion, and smoke tests together.

## Dependency mirror

The adapter is a standalone downstream crate, so its Cargo manifest declares
the dependencies and features required by registered upstream source. The root
workspace excludes the upstream workspace and resolves the downstream crates
through one `Cargo.lock`.

After an upstream Cargo change, compare its dependencies and features with the
adapter manifest. Add what the registered module graph now requires and remove
what an audited rewrite made unnecessary. `scripts/update_upstream.py` aligns
the adapter version and refreshes the root lock, but it does not rewrite this
dependency mirror.

The adapter crate version follows the embedded upstream engine version. The Python and PyO3 crate version follows the pyagentbrowser release.

Read [the downstream wrapper model](repository-model.md) before deciding whether
a change belongs in upstream, the generated adapter, the PyO3 crate, or Python.
