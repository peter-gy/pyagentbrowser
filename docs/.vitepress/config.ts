import {
  defineConfig,
  type DefaultTheme,
  type HeadConfig,
  type Plugin,
} from "vitepress";
import llmstxt from "vitepress-plugin-llms";

import {
  conceptItems,
  guideItems,
  introductionItems,
  referenceItems,
  routes,
} from "./routes.ts";

const repository = "https://github.com/peter-gy/pyagentbrowser";
const defaultSiteUrl = "https://peter-gy.github.io/pyagentbrowser/";
const description =
  "Python SDK for the native agent-browser engine with typed actions, browser lifecycle, safety policy, and before-and-after evidence.";

function normalizeBasePath(value: string | undefined): string {
  const name = value?.trim().replace(/^\/+|\/+$/g, "");
  return name ? `/${name}` : "";
}

function normalizeSiteUrl(value: string | undefined): URL {
  const configured = value?.trim() || defaultSiteUrl;
  return new URL(`${configured.replace(/\/+$/, "")}/`);
}

const basePath = normalizeBasePath(process.env.BASE_PATH);
const base = basePath ? `${basePath}/` : "/";
const siteUrl = normalizeSiteUrl(process.env.SITE_URL);
const socialImage = new URL("og.png", siteUrl).href;
const llmsDomain = basePath ? siteUrl.origin : siteUrl.href.replace(/\/$/, "");
const devPort = process.env.PORT ? Number(process.env.PORT) : undefined;
const themeSidebar: DefaultTheme.SidebarItem[] = [
  { text: "Introduction", collapsed: false, items: introductionItems },
  { text: "Core concepts", collapsed: false, items: conceptItems },
  { text: "Guides", collapsed: false, items: guideItems },
  { text: "Reference", collapsed: true, items: referenceItems },
  { text: "Troubleshooting", link: routes.troubleshooting },
];
const llmsSidebar: DefaultTheme.Sidebar = [
  {
    text: "Introduction",
    items: [
      { text: "pyagentbrowser", link: routes.home },
      ...introductionItems,
    ],
  },
  ...themeSidebar.slice(1),
];
// vitepress-plugin-llms returns two Vite plugins that run together to emit
// per-page Markdown, llms.txt, and llms-full.txt.
const llmsPlugins = llmstxt({
  domain: llmsDomain,
  excludeIndexPage: false,
  sidebar: llmsSidebar,
}) as [Plugin, Plugin];

function withBase(path: string): string {
  return `${basePath}/${path.replace(/^\/+/, "")}`;
}

function canonicalUrl(page: string): string {
  const source = page.replace(/^\/+/, "");
  const route = /(^|\/)index\.md$/.test(source)
    ? source.replace(/(^|\/)index\.md$/, "$1")
    : source.replace(/\.md$/, ".html");
  return new URL(route, siteUrl).href;
}

export default defineConfig({
  base,
  description,
  head: [
    [
      "link",
      {
        rel: "icon",
        type: "image/svg+xml",
        media: "(prefers-color-scheme: light)",
        href: withBase("brand/pyagentbrowser-mark-light.svg"),
      },
    ],
    [
      "link",
      {
        rel: "icon",
        type: "image/svg+xml",
        media: "(prefers-color-scheme: dark)",
        href: withBase("brand/pyagentbrowser-mark-dark.svg"),
      },
    ],
    ["meta", { name: "theme-color", content: "#3776ab" }],
  ],
  lang: "en-US",
  lastUpdated: true,
  sitemap: { hostname: siteUrl.href },
  title: "pyagentbrowser",
  titleTemplate: ":title | pyagentbrowser",
  transformPageData(pageData) {
    const canonical = canonicalUrl(pageData.relativePath);
    const summary = pageData.description || description;
    const pageTitle = pageData.title
      ? `${pageData.title} | pyagentbrowser`
      : "pyagentbrowser";
    ((pageData.frontmatter.head ??= []) as HeadConfig[]).push(
      ["link", { rel: "canonical", href: canonical }],
      ["meta", { property: "og:type", content: "website" }],
      ["meta", { property: "og:site_name", content: "pyagentbrowser" }],
      ["meta", { property: "og:locale", content: "en_US" }],
      ["meta", { property: "og:title", content: pageTitle }],
      ["meta", { property: "og:description", content: summary }],
      ["meta", { property: "og:url", content: canonical }],
      ["meta", { property: "og:image", content: socialImage }],
      ["meta", { property: "og:image:width", content: "2400" }],
      ["meta", { property: "og:image:height", content: "1260" }],
      [
        "meta",
        {
          property: "og:image:alt",
          content:
            "pyagentbrowser native browser engine for agents, embedded in Python",
        },
      ],
      ["meta", { name: "twitter:card", content: "summary_large_image" }],
      ["meta", { name: "twitter:title", content: pageTitle }],
      ["meta", { name: "twitter:description", content: summary }],
      ["meta", { name: "twitter:image", content: socialImage }],
    );
  },
  themeConfig: {
    editLink: {
      pattern: `${repository}/edit/main/docs/:path`,
      text: "Edit this page on GitHub",
    },
    footer: {
      message: "Released under the Apache License 2.0.",
      copyright: "Copyright © Péter Ferenc Gyarmati",
    },
    logo: {
      alt: "pyagentbrowser",
      light: "/brand/pyagentbrowser-lockup-horizontal-light.svg",
      dark: "/brand/pyagentbrowser-lockup-horizontal-dark.svg",
    },
    nav: [
      { text: "Start", link: routes.gettingStarted },
      { text: "Concepts", link: routes.runtimeModel },
      { text: "Guides", link: routes.interact },
      { text: "Reference", link: routes.browserReference },
      { text: "Troubleshooting", link: routes.troubleshooting },
    ],
    outline: [2, 3],
    search: { provider: "local" },
    sidebar: themeSidebar,
    siteTitle: false,
    socialLinks: [{ icon: "github", link: repository }],
  },
  vite: {
    plugins: llmsPlugins,
    server: {
      host: "127.0.0.1",
      port: devPort,
      strictPort: devPort !== undefined,
    },
  },
});
