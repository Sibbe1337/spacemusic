import { e as jsx, r as React, aF as Helmet } from "./vendor-DhPEFgb5.js";
import { b as useParams } from "./vendor-router-D1jo5eb_.js";
import { N as Navbar } from "./Navbar-DK5bZPep.js";
import { F as Footer } from "./Footer-CiCbq8u0.js";
import { S as SEOHead } from "./SEOHead-C4J8_WVH.js";

const article = __ARTICLE__;
const styles = __ARTICLE_STYLES__;
const LegacyBlogPost = React.lazy(() => import("./__LEGACY_BLOG_MODULE__"));

function ArticlePage() {
  React.useEffect(() => {
    const target = document.getElementById(window.location.hash.slice(1));
    if (target) target.scrollIntoView();
    else window.scrollTo(0, 0);
  }, []);

  return jsx.jsxs(React.Fragment, {
    children: [
      jsx.jsx(SEOHead, {
        title: article.seoTitle,
        description: article.description,
        canonical: article.url,
        type: "article",
        image: article.image,
        schema: article.schema,
      }),
      jsx.jsxs(Helmet, {
        children: [
          jsx.jsx("style", { id: "space-blog-style", children: styles }),
          jsx.jsx("meta", { property: "og:image:width", content: "1730" }),
          jsx.jsx("meta", { property: "og:image:height", content: "909" }),
          jsx.jsx("meta", { property: "og:image:type", content: "image/png" }),
          jsx.jsx("meta", { property: "og:image:alt", content: article.imageAlt }),
          jsx.jsx("meta", { name: "twitter:image:alt", content: article.imageAlt }),
          jsx.jsx("meta", { property: "article:published_time", content: article.datePublished }),
          jsx.jsx("meta", { property: "article:modified_time", content: article.dateModified }),
        ],
      }),
      jsx.jsx(Navbar, {}),
      jsx.jsx("main", {
        className: "space-blog-article",
        children: jsx.jsxs("article", {
          children: [
            jsx.jsxs("header", {
              className: "space-blog-header",
              children: [
                jsx.jsxs("nav", {
                  "aria-label": "Breadcrumb",
                  children: [
                    jsx.jsx("a", { href: "/", children: "SPACE" }),
                    jsx.jsx("span", { "aria-hidden": "true", children: "/" }),
                    jsx.jsx("span", { children: article.category }),
                  ],
                }),
                jsx.jsx("h1", { children: article.title }),
                jsx.jsxs("p", {
                  className: "space-blog-meta",
                  children: [
                    "By ",
                    jsx.jsx("a", { href: "/about/", children: article.author }),
                    " | ",
                    jsx.jsx("time", { dateTime: article.datePublished, children: article.displayDate }),
                    ` | ${article.readingTime} min read`,
                  ],
                }),
              ],
            }),
            jsx.jsx("div", {
              className: "space-blog-content",
              dangerouslySetInnerHTML: { __html: article.introduction },
            }),
            jsx.jsxs("nav", {
              className: "space-blog-toc",
              "aria-label": "In this article",
              children: [
                jsx.jsx("p", { children: "In this article" }),
                jsx.jsx("ol", {
                  children: article.headings.map((heading) => jsx.jsx("li", {
                    children: jsx.jsx("a", { href: `#${heading.id}`, children: heading.text }),
                  }, heading.id)),
                }),
              ],
            }),
            jsx.jsx("div", {
              className: "space-blog-content",
              dangerouslySetInnerHTML: { __html: article.body },
            }),
          ],
        }),
      }),
      jsx.jsx(Footer, {}),
    ],
  });
}

export default function BlogRoute() {
  const { slug } = useParams();
  return jsx.jsx(slug === article.slug ? ArticlePage : LegacyBlogPost, {});
}
