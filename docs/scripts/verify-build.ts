import { readdir, readFile, stat } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { allRoutes } from "../.vitepress/routes.ts";

const docsDir = dirname(dirname(fileURLToPath(import.meta.url)));
const distDir = join(docsDir, ".vitepress", "dist");
const defaultSiteUrl = "https://peter-gy.github.io/pyagentbrowser/";
const baseName = process.env.BASE_PATH?.trim().replace(/^\/+|\/+$/g, "");
const basePath = baseName ? `/${baseName}` : "";
const siteUrl = new URL(
  `${(process.env.SITE_URL?.trim() || defaultSiteUrl).replace(/\/+$/, "")}/`,
);
const socialImage = new URL("og.png", siteUrl).href;
const publicPath = (path: string): string => `${basePath}/${path.replace(/^\/+/, "")}`;

function check(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

async function isFile(path: string): Promise<boolean> {
  try {
    const details = await stat(path);
    return details.isFile() && details.size > 0;
  } catch {
    return false;
  }
}

async function markdownFiles(directory: string): Promise<string[]> {
  const files: string[] = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === "public" || entry.name === ".vitepress") {
      continue;
    }
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await markdownFiles(path)));
    if (entry.isFile() && entry.name.endsWith(".md")) files.push(path);
  }
  return files;
}

function sourceRoute(path: string): string {
  const source = relative(docsDir, path).replaceAll("\\", "/");
  if (source === "index.md") return "/";
  return `/${source.replace(/\.md$/, "").replace(/\/index$/, "")}`;
}

function outputPath(route: string): string {
  if (route === "/") return join(distDir, "index.html");
  return join(distDir, `${route.slice(1)}.html`);
}

function sourceOutputPath(path: string): string {
  const source = relative(docsDir, path).replaceAll("\\", "/");
  return join(distDir, source.replace(/\.md$/, ".html"));
}

function sourceMarkdownOutputPath(path: string): string {
  return join(distDir, relative(docsDir, path));
}

function canonicalUrl(route: string): string {
  const path = route === "/" ? "" : `${route.slice(1)}.html`;
  return new URL(path, siteUrl).href;
}

const markdown = await markdownFiles(docsDir);
const sources = markdown.map(sourceRoute).sort();
const configured = [...allRoutes].sort();
check(
  JSON.stringify(sources) === JSON.stringify(configured),
  `Navigation mismatch: sources=${JSON.stringify(sources)} configured=${JSON.stringify(configured)}`,
);

for (const source of markdown) {
  check(await isFile(sourceOutputPath(source)), `Missing built page for ${relative(docsDir, source)}`);
  check(
    await isFile(sourceMarkdownOutputPath(source)),
    `Missing generated Markdown for ${relative(docsDir, source)}`,
  );
}

const llms = await readFile(join(distDir, "llms.txt"), "utf8");
const llmsFull = await readFile(join(distDir, "llms-full.txt"), "utf8");
const routeFromMarkdownUrl = (url: string): string => {
  const path = url.slice(siteUrl.href.length);
  if (path === "index.md") return "/";
  return `/${path.replace(/\.md$/, "").replace(/\/index$/, "")}`;
};
const llmsRoutes = [...llms.matchAll(/https?:\/\/[^\s]+/g)]
  .map((match) => match[0])
  .map((url) => url.replace(/[):,]+$/, ""))
  .filter((url) => url.startsWith(siteUrl.href) && url.endsWith(".md"))
  .map(routeFromMarkdownUrl)
  .sort();
check(
  JSON.stringify(llmsRoutes) === JSON.stringify(configured),
  `llms.txt mismatch: listed=${JSON.stringify(llmsRoutes)} configured=${JSON.stringify(configured)}`,
);
const llmsFullUrls = [
  ...llmsFull.matchAll(
    /^url:\s+(?:'(https?:\/\/[^']+\.md)'|(https?:\/\/\S+\.md)|>-\n\s+(https?:\/\/\S+\.md))$/gm,
  ),
]
  .map((match) => match[1] ?? match[2] ?? match[3])
  .filter((url): url is string => url !== undefined);
const llmsFullRoutes = llmsFullUrls.map(routeFromMarkdownUrl).sort();
check(
  JSON.stringify(llmsFullRoutes) === JSON.stringify(configured),
  `llms-full.txt mismatch: listed=${JSON.stringify(llmsFullRoutes)} configured=${JSON.stringify(configured)}`,
);
check(
  llmsFull.includes("# Browser controller reference"),
  "llms-full.txt is missing the browser controller reference",
);

const requiredAssets = [
  "og.png",
  "robots.txt",
  "llms.txt",
  "llms-full.txt",
  "sitemap.xml",
  "brand/pyagentbrowser-mark-light.svg",
  "brand/pyagentbrowser-mark-dark.svg",
  "brand/pyagentbrowser-lockup-horizontal-light.svg",
  "brand/pyagentbrowser-lockup-horizontal-dark.svg",
  "icons/scan-eye-light.svg",
  "icons/scan-eye-dark.svg",
  "icons/workflow-light.svg",
  "icons/workflow-dark.svg",
  "icons/code-xml-light.svg",
  "icons/code-xml-dark.svg",
  "icons/LICENSE",
];
for (const asset of requiredAssets) {
  check(await isFile(join(distDir, asset)), `Missing public asset: ${asset}`);
}

const home = await readFile(join(distDir, "index.html"), "utf8");
for (const expected of [
  socialImage,
  `rel="canonical" href="${siteUrl.href}"`,
  "property=\"og:image\"",
  `property="og:url" content="${siteUrl.href}"`,
  "name=\"twitter:card\"",
  "media=\"(prefers-color-scheme: light)\"",
  "media=\"(prefers-color-scheme: dark)\"",
  publicPath("brand/pyagentbrowser-mark-light.svg"),
  publicPath("brand/pyagentbrowser-mark-dark.svg"),
  publicPath("brand/pyagentbrowser-lockup-horizontal-light.svg"),
  publicPath("brand/pyagentbrowser-lockup-horizontal-dark.svg"),
  publicPath("icons/scan-eye-light.svg"),
  publicPath("icons/scan-eye-dark.svg"),
  publicPath("icons/workflow-light.svg"),
  publicPath("icons/workflow-dark.svg"),
  publicPath("icons/code-xml-light.svg"),
  publicPath("icons/code-xml-dark.svg"),
  `href="${publicPath("concepts/evidence.html")}"`,
  `href="${publicPath("concepts/runtime-model.html")}"`,
  `href="${publicPath("guides/native-protocol.html")}"`,
]) {
  check(home.includes(expected), `Built home page is missing ${expected}`);
}

check(
  home.includes(`href="${publicPath("assets/")}`),
  `Built home page is missing a stylesheet under ${publicPath("assets/")}`,
);
check(
  home.includes(`src="${publicPath("assets/")}`),
  `Built home page is missing a script under ${publicPath("assets/")}`,
);

const nestedRoute = "/concepts/safety";
const nested = await readFile(outputPath(nestedRoute), "utf8");
for (const expected of [
  `rel="canonical" href="${canonicalUrl(nestedRoute)}"`,
  `property="og:url" content="${canonicalUrl(nestedRoute)}"`,
  `property="og:image" content="${socialImage}"`,
]) {
  check(nested.includes(expected), `Built nested page is missing ${expected}`);
}

const sitemap = await readFile(join(distDir, "sitemap.xml"), "utf8");
for (const route of configured) {
  check(sitemap.includes(`<loc>${canonicalUrl(route)}</loc>`), `Sitemap is missing ${route}`);
}

const robots = await readFile(join(distDir, "robots.txt"), "utf8");
const sitemapUrl = new URL("sitemap.xml", siteUrl).href;
check(robots.includes(`Sitemap: ${sitemapUrl}`), `robots.txt is missing ${sitemapUrl}`);

if (process.env.SITE_URL?.trim()) {
  const sitePath = siteUrl.pathname.replace(/\/+$/, "");
  check(
    sitePath === basePath,
    `SITE_URL path ${sitePath || "/"} does not match BASE_PATH ${basePath || "/"}`,
  );
}

console.log(
  `Verified ${configured.length} pages and ${requiredAssets.length} public assets at base ${basePath || "/"}.`,
);
