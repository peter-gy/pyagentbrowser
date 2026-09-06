# Documentation

The public documentation is a [VitePress](https://vitepress.dev/) static site rooted at `docs/`. Contributor implementation notes remain in `development_docs/`.

## Reader boundaries

Public docs own installation, first success, the runtime mental model, user workflows, API contracts, errors, compatibility, and troubleshooting.

Contributor docs own source boundaries, adapter generation, safety enforcement, lifecycle internals, testing, packaging, and release operations.

## Local workflow

```bash
make docs-install
make docs-dev
```

[Portless](https://portless.sh/) assigns the VitePress development server an
available port and exposes it at `https://docs.pyagentbrowser.localhost/`. A
linked Git worktree receives a branch-prefixed subdomain, so concurrent
workspaces do not collide. Use the URL printed by `make docs-dev`.

On its first HTTPS run, Portless may request local administrator access to bind
port 443 and trust its local certificate authority. Run
`pnpm --dir docs dev:server` when a direct VitePress server is required.

Local development serves from `/`. The GitHub Pages workflow passes the
deployed base path and site URL reported by `actions/configure-pages` into the
production build.

Run the complete docs gate with:

```bash
make docs-check
```

The gate verifies that every contributor page is linked from
`development_docs/index.md` and checks its local links. It then type-checks the
TypeScript configuration, builds every public page, lets VitePress reject dead
site links, checks that every public Markdown page appears in navigation, and
verifies metadata, assets, per-page Markdown, `llms.txt`, and `llms-full.txt`.

## Information architecture

- Introduction explains what the project is, why its boundaries exist, and how to reach first success.
- Concepts define the runtime, evidence, and safety models.
- Guides are organized by user task.
- Reference pages are organized by public object and namespace.
- Troubleshooting begins from observable failures and typed errors.

Use `pyagentbrowser` for the distribution, `agentbrowser` for the import package, and `agent-browser` for the embedded upstream engine. Use snapshot-scoped ref, browser controller, native session, active tab, native frame, direct CDP handle, explicit saved state, and keyed restore according to [the contributor vocabulary](index.md#canonical-vocabulary).

## Assets and metadata

`docs/public/brand` contains the generated light and dark SVG and PNG variants. `docs/public/og.png` is the canonical social image. The VitePress configuration selects themed navigation logos and favicons, emits canonical and social metadata, enables local search, and generates a sitemap.

`vitepress-plugin-llms` emits one Markdown file per public page plus `llms.txt`
and `llms-full.txt`. Its navigation derives from the same route groups as the
rendered sidebar. The Pages base path and site URL also determine its generated
links.

Maintainer brand exports are reviewed source assets. Contributors validate the public files through the docs build. A brand change requires a maintainer-provided export whose dimensions, SVG structure, and rendered appearance have been checked before it enters `docs/public`.

## Validation

Check the production build at desktop and narrow widths. Exercise light and dark themes, navigation, search, code copy, nested-route refresh, 404 behavior, asset loading, and browser console errors.

Review changed Markdown against the repository documentation rules before
handoff. Verify runnable Python examples through the active checkout or a
freshly built wheel.
