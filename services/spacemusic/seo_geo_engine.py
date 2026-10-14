"""Unified re-export module for SPACE SEO, GEO, JSON-LD, and Interactive Calculator Widget."""

from __future__ import annotations

from .seo_calculator_widget import (
    InteractiveCalculatorTeaserRequest,
    InteractiveCalculatorTeaserResponse,
    evaluate_interactive_calculator_teaser,
    render_embeddable_calculator_html,
    render_embeddable_calculator_widget_js,
)
from .seo_geo_data import (
    ALL_GENRE_COHORTS,
    INSTITUTIONAL_BUYERS,
    LANDING_PAGES_BY_SLUG,
    LAST_MODIFIED,
    SEO_PAGE_METADATA_OVERRIDES,
    SITE_URL,
    LandingPageContent,
    PageSeoMetadata,
    build_page_jsonld_schemas,
    export_seo_static_bundle,
    generate_cloudflare_redirects,
    get_backlink_outreach_kit,
    get_brand_facts_payload,
    get_indie_catalog_benchmark_report_2026,
    render_llms_full_txt,
    render_llms_txt,
    render_pricing_md,
    render_sitemap_xml,
    resolve_canonical_redirect,
)

__all__ = [
    "ALL_GENRE_COHORTS",
    "INSTITUTIONAL_BUYERS",
    "LANDING_PAGES_BY_SLUG",
    "LAST_MODIFIED",
    "SEO_PAGE_METADATA_OVERRIDES",
    "SITE_URL",
    "InteractiveCalculatorTeaserRequest",
    "InteractiveCalculatorTeaserResponse",
    "LandingPageContent",
    "PageSeoMetadata",
    "build_page_jsonld_schemas",
    "evaluate_interactive_calculator_teaser",
    "export_seo_static_bundle",
    "generate_cloudflare_redirects",
    "get_backlink_outreach_kit",
    "get_brand_facts_payload",
    "get_indie_catalog_benchmark_report_2026",
    "render_embeddable_calculator_html",
    "render_embeddable_calculator_widget_js",
    "render_llms_full_txt",
    "render_llms_txt",
    "render_pricing_md",
    "render_sitemap_xml",
    "resolve_canonical_redirect",
]
