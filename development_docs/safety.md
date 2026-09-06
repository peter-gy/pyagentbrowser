# Safety architecture

Session containment is an ordered, multi-layer contract. A new URL-bearing action must preserve every applicable stage.

```text
public option validation
  -> Python command validation
  -> native browser-level containment
  -> confirmation pause
  -> confirmation replay revalidation
  -> response and exported-state filtering
```

## Launch constraints

`LaunchConfiguration` rejects modes that can restore or open a page before containment begins. `allowed_domains` conflicts with profiles, storage-state replay, keyed restore, CDP attachment, automatic connection, iOS and Safari providers, and browser arguments that open existing pages.

Containment must start on a fresh controllable browser context before page, popup, frame, worker, or WebRTC scripts run.

## Python command policy

`DomainAllowlist` validates direct URLs, host-qualified patterns, cookie writes, permission origins, frame targets, scripts, styles, network routes, waits, and raw command fields before dispatch.

Exact entries match one host. A wildcard suffix authorizes the root host and its subdomains. Wildcard request patterns require matching wildcard authority.

Successful cookie responses are filtered in memory before the result reaches
the caller. A contained `state_save` writes the native file first, then Python
reads, filters, and rewrites its cookies and origins in place before returning.
A failure in this post-write stage can leave the created file and must surface
to the caller. Unscoped export and cookie clear operations require their
explicit unsafe flag.

## Native containment

The native engine receives allowed domains, the action-policy path, and exact confirmation action names. The browser-level domain filter enforces requests that page scripts can initiate before Python observes them.

Raw native launch actions cannot silently weaken an active allowlist. A successful explicitly authorized launch can adopt a new policy through the same session transition rules.

## Confirmation replay

`NativeSession` keeps the initiating JSON command and Python domain policy under the confirmation ID. The adapter validates the ID, reloads current action policy, and rechecks target-bearing inputs against current domain policy before replay.

`PendingAction` retains the typed decoder and higher-level completion chain. A confirmed ref mutation still runs its wait, captures the next snapshot, and computes its diff.

Denial, failed replay, and mismatched IDs cannot adopt pending policy state.

## Review checklist for a native action

1. Identify every URL, origin, host-qualified pattern, cookie, file, or target field.
2. Add Python pre-dispatch validation where caller input can be checked.
3. Confirm browser-level containment covers page-initiated effects.
4. Preserve confirmation identity and replay revalidation.
5. Filter returned cookies or state records when they can cross the allowlist.
6. Define any unsafe override at the narrowest operation.
7. Add tests for typed and raw calls, success and failure, and confirmation replay.
