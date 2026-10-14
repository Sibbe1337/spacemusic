const siteUrl = (process.env.SITE_URL || "https://spacemusic.io").replace(/\/$/, "");
const expectedUrls = Number(process.env.EXPECTED_SITEMAP_URLS || 137);
const concurrency = 8;

function attribute(tag, name) {
  const match = tag.match(new RegExp(`${name}=["']([^"']+)["']`, "i"));
  return match?.[1] || "";
}

async function fetchPage(url, options = {}) {
  return fetch(url, {
    redirect: "manual",
    headers: { "User-Agent": "SpaceMusic SEO safety check" },
    ...options,
  });
}

function sitemapUrls(xml) {
  return [...xml.matchAll(/<loc>\s*([^<]+?)\s*<\/loc>/gi)].map((match) => match[1]);
}

async function checkRoute(url) {
  try {
    const response = await fetchPage(url);
    const location = response.headers.get("location");
    if (response.status >= 300 && response.status < 400) {
      return `${url} redirects to ${location || "an unknown location"}`;
    }
    if (response.status !== 200) {
      return `${url} returned HTTP ${response.status}`;
    }
    if (/noindex|\bnone\b/i.test(response.headers.get("x-robots-tag") || "")) {
      return `${url} contains a noindex HTTP header in production`;
    }

    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("text/html")) return null;

    const html = await response.text();
    const canonicalTags = html.match(/<link\b[^>]*\brel=["'][^"']*canonical[^"']*["'][^>]*>/gi) || [];
    const canonicals = canonicalTags.map((tag) => attribute(tag, "href")).filter(Boolean);
    if (canonicals.length !== 1) {
      return `${url} has ${canonicals.length} canonical tags`;
    }
    if (canonicals[0] !== url) {
      return `${url} canonical is ${canonicals[0]}`;
    }

    const robotsTags = html.match(/<meta\b[^>]*\bname=["']robots["'][^>]*>/gi) || [];
    if (robotsTags.some((tag) => /noindex/i.test(attribute(tag, "content")))) {
      return `${url} contains noindex in production`;
    }
    if (!/<h1\b/i.test(html)) {
      return `${url} has no h1`;
    }
  } catch (error) {
    return `${url} failed: ${error instanceof Error ? error.message : String(error)}`;
  }
  return null;
}

const issues = [];
const sitemapResponse = await fetchPage(`${siteUrl}/sitemap.xml`);
if (sitemapResponse.status !== 200) {
  issues.push(`sitemap.xml returned HTTP ${sitemapResponse.status}`);
} else {
  const sitemap = await sitemapResponse.text();
  const urls = sitemapUrls(sitemap);
  const uniqueUrls = new Set(urls);
  if (urls.length !== expectedUrls) {
    issues.push(`sitemap contains ${urls.length} URLs; expected ${expectedUrls}`);
  }
  if (uniqueUrls.size !== urls.length) {
    issues.push("sitemap contains duplicate URLs");
  }
  if (urls.some((url) => !url.startsWith(`${siteUrl}/`))) {
    issues.push("sitemap contains a URL outside the production origin");
  }

  for (let index = 0; index < urls.length; index += concurrency) {
    const batch = urls.slice(index, index + concurrency);
    const results = await Promise.all(batch.map(checkRoute));
    issues.push(...results.filter(Boolean));
  }
}

const robotsResponse = await fetchPage(`${siteUrl}/robots.txt`);
if (robotsResponse.status !== 200) {
  issues.push(`robots.txt returned HTTP ${robotsResponse.status}`);
} else {
  const robots = await robotsResponse.text();
  if (!new RegExp(`^Sitemap:\\s*${siteUrl}/sitemap\\.xml\\s*$`, "im").test(robots)) {
    issues.push("robots.txt does not point to the production sitemap");
  }
}

if (issues.length) {
  console.error(`SEO safety check failed with ${issues.length} issue(s):`);
  for (const issue of issues.slice(0, 40)) console.error(`- ${issue}`);
  process.exitCode = 1;
} else {
  console.log(`SEO safety check passed: ${expectedUrls} sitemap URLs, canonical and robots checks clean.`);
}
