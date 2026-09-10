import type { DefaultTheme } from "vitepress";

export const routes = {
  home: "/",
  introduction: "/introduction",
  why: "/why",
  gettingStarted: "/getting-started",
  migration: "/migration",
  runtimeModel: "/concepts/runtime-model",
  evidence: "/concepts/evidence",
  safety: "/concepts/safety",
  interact: "/guides/interact",
  readCapture: "/guides/read-and-capture",
  tabsState: "/guides/tabs-and-state",
  networkDiagnostics: "/guides/network-and-diagnostics",
  cdp: "/guides/cdp",
  async: "/guides/async",
  webmcp: "/guides/webmcp",
  dashboard: "/guides/dashboard",
  agentSkills: "/guides/agent-skills",
  codeMode: "/guides/code-mode",
  nativeProtocol: "/guides/native-protocol",
  extensions: "/guides/extensions",
  browserReference: "/reference/browser",
  namespacesReference: "/reference/namespaces",
  modelsReference: "/reference/models",
  environmentReference: "/reference/environment",
  troubleshooting: "/troubleshooting",
} as const;

export const introductionItems = [
  { text: "What is pyagentbrowser?", link: routes.introduction },
  { text: "Why pyagentbrowser?", link: routes.why },
  { text: "Get started", link: routes.gettingStarted },
  { text: "Migrate scoped agents", link: routes.migration },
] satisfies DefaultTheme.SidebarItem[];

export const conceptItems = [
  { text: "Runtime model", link: routes.runtimeModel },
  { text: "Snapshots and evidence", link: routes.evidence },
  { text: "Safety model", link: routes.safety },
] satisfies DefaultTheme.SidebarItem[];

export const guideItems = [
  { text: "Interact with pages", link: routes.interact },
  { text: "Read and capture", link: routes.readCapture },
  { text: "Tabs and state", link: routes.tabsState },
  { text: "Network and diagnostics", link: routes.networkDiagnostics },
  { text: "Direct CDP", link: routes.cdp },
  { text: "Async applications", link: routes.async },
  { text: "WebMCP tools", link: routes.webmcp },
  { text: "Dashboard observation", link: routes.dashboard },
  { text: "Agent skills and code mode", link: routes.agentSkills },
  { text: "Code-mode integration", link: routes.codeMode },
  { text: "Raw native protocol", link: routes.nativeProtocol },
  { text: "Compose extensions", link: routes.extensions },
] satisfies DefaultTheme.SidebarItem[];

export const referenceItems = [
  { text: "Browser controllers", link: routes.browserReference },
  { text: "Capability namespaces", link: routes.namespacesReference },
  { text: "Models and errors", link: routes.modelsReference },
  { text: "Environment and platforms", link: routes.environmentReference },
] satisfies DefaultTheme.SidebarItem[];

export const allRoutes = Object.values(routes);
