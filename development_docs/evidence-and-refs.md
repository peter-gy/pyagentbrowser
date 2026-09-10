# Evidence and refs

`features/evidence/` turns native accessibility snapshots into action-scoped
evidence. It owns snapshot capture, ref lookup,
wait composition, transition diffs, stale-ref recovery, and partial-failure
reporting.

## Evidence objects

| Object                  | Contract                                                 |
| ----------------------- | -------------------------------------------------------- |
| `SnapshotSpec`          | Repeatable capture settings carried by a snapshot        |
| `Snapshot`              | Captured text, metadata, and snapshot-scoped refs        |
| `Ref`                   | One element identity resolved from one snapshot          |
| `Wait`                  | Post-action condition applied before the next snapshot   |
| `ActionResult`          | Ref, before snapshot, after snapshot, and their diff     |
| `ActionTransitionError` | A completed mutation whose wait or evidence stage failed |
| `DocumentScope`         | Page-target and frame identity for one document handle   |
| `EvidenceManifest`      | Captures, deliveries, assessments, and assertions        |

A ref belongs to the snapshot that produced it. It stores the source snapshot,
native ref ID, selector, role, name, and raw node metadata. A later page state
can invalidate the native ID even while the Python object still exists.

The native response supplies the ref-map generation stored by each snapshot.
Ref commands carry that generation into dispatch so a later observation cannot
reuse an ID for a different element. Snapshot refresh and transition capture
retain the producing page and frame handle.

`Snapshot.document` and `Ref.document` expose that handle. Evidence commands use
its executor, which applies document scope and the captured ref generation.

Typed ref commands resolve the captured node identity and reject detached
nodes. Use `ref.refresh()` to select from a new snapshot after replacement.
The native escape hatch retains the pinned engine's role-and-name fallback.

## Action transition

```text
source snapshot and ref
  -> native mutation
  -> requested wait conditions
  -> next snapshot with the same SnapshotSpec
  -> snapshot diff
  -> ActionResult
```

The mutation and evidence stages have different failure semantics. When the
native mutation succeeds but a wait, next snapshot, or diff fails,
`ActionTransitionError` preserves the original ref and source snapshot and
states that the action completed. Callers can then inspect current browser
state without guessing whether to repeat the mutation.

Confirmation can pause at the mutation, wait, or after-snapshot stage. The
pending action retains the typed decoder and all remaining work. Confirming it
continues the same high-level operation and returns its declared result type.

## Queries and stale refs

`Snapshot.one()` requires one matching ref. `Snapshot.all()` returns every
match. `Query` and `Queries` retain criteria so a caller can resolve them against
fresh snapshots.

An engine error with the owned stale-ref or unknown-ref code becomes
`StaleRefError` or `AsyncStaleRefError`. The error retains the ref and exposes a
refresh path using its captured role and name or caller-supplied criteria. Keep
error-code mapping in the native and Python layers aligned.

## Wait composition

Ref actions accept one `Wait` value. A wait can match text, a URL pattern, or a
page load state. `Wait.all()` applies several conditions in their declared
order. The after snapshot is captured after every condition has completed.

The same `SnapshotSpec` is reused for before and after snapshots so their diff
compares the same representation. A change to default capture settings,
snapshot decoding, or wait order therefore changes the evidence contract.

## Review checklist

1. Keep synchronous and asynchronous action pipelines semantically aligned.
2. Preserve the source snapshot and ref across success, confirmation, and
   partial failure.
3. Keep mutation completion distinguishable from evidence-stage failure.
4. Reuse the source `SnapshotSpec` for the after snapshot.
5. Map native stale-ref codes to the typed recovery error.
6. Assert the public transition result rather than private call order.

Use `make test-sdk` for composition, decoding, confirmation, stale-ref, and
partial-failure contracts. Add `make test-integration` when the behavior depends
on a real page transition.
