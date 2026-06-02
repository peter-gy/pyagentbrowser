# Security Policy

Report security issues privately through GitHub Security Advisories for this
repository. Do not open public issues for vulnerabilities.

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.27.x pre-releases | Security fixes for Python-owned bridge, package, allowlist, confirmation, and dashboard-session behavior |
| Older 0.x pre-releases | Upgrade to the newest pre-release before reporting reproducible issues |

## Sensitive Surfaces

Treat reports as security-sensitive when they involve:

- domain allowlist bypasses
- action policy or confirmation bypasses
- CDP endpoint misuse or unintended target access
- cookie, local storage, session storage, or state-file leakage
- downloads or filesystem artifacts written outside the requested path
- profile, storage-state, extension, or proxy handling
- dashboard controls that affect the host Python process beyond observability.

## Ownership Boundary

`pyagentbrowser` embeds upstream `agent-browser` native code. Python-owned
security issues include packaging, Python exception handling, confirmation
replay exposure, default-session behavior, dashboard SDK integration, and
anything introduced by the Python/Rust bridge.

Upstream-owned issues in the native engine should be reported upstream too, but
this repository may carry a narrow generated Native Safety Patch when the Python
SDK would otherwise expose known unsafe native behavior. The policy and accepted
patches are documented in
[docs/adr/0001-native-safety-patches.md](docs/adr/0001-native-safety-patches.md).

For non-security bugs, use the public issue tracker.
