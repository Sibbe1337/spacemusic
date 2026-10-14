# Approved editorial release: fresh performance gate

Measured September 16, 2026, 12:13-12:19 UTC (14:13-14:19 CEST).
PageSpeed Insights UI, homepage, mobile mode. Three requested reports per
version. Matching displayed environment: emulated Moto G Power, slow 4G,
initial page load, Lighthouse 13.4.1, HeadlessChromium 151.0.7922.173.
Exact metrics were read from each report's visible score-calculator link.

| Version / run | LCP ms | TBT ms | CLS | Performance score | Report |
| --- | ---: | ---: | ---: | ---: | --- |
| Production before 1 | 2851 | 992 | 0 | 66 | https://pagespeed.web.dev/analysis/https-spacemusic-io/dis0eo7dnc?form_factor=mobile |
| Production before 2 | 2851 | 0 | 0 | 94 | https://pagespeed.web.dev/analysis/https-spacemusic-io/u8iuxluem9?form_factor=mobile |
| Production before 3 | 2851 | 0 | 0 | 90 | https://pagespeed.web.dev/analysis/https-spacemusic-io/jqb36tfj0j?form_factor=mobile |
| Candidate 1 | 2701 | 0 | 0 | 91 | https://pagespeed.web.dev/analysis/https-b5189220-spacemusic-a6n-pages-dev/eao48upb36?form_factor=mobile |
| Candidate 2 | 1501 | 0 | 0 | 100 | https://pagespeed.web.dev/analysis/https-b5189220-spacemusic-a6n-pages-dev/c6ubabgjiw?form_factor=mobile |
| Candidate 3 | 2701 | 0 | 0 | 91 | https://pagespeed.web.dev/analysis/https-b5189220-spacemusic-a6n-pages-dev/6emtfwd5np?form_factor=mobile |

Median LCP: **2851 ms before, 2701 ms candidate**, difference -150 ms (-5.26%).
The agreed regression gate (increase exceeding both 10% and 250 ms) is not
triggered. Median TBT and CLS are zero in both groups. Retain the slow first
baseline run and fast second candidate run; they were not discarded.

This is a homepage release-regression check, not a three-run article benchmark
or real-user improvement claim. Origins differ (public domain versus preview),
and PageSpeed exposes no CrUX field data for these checks. The two versions
retain the existing contrast warning (96 accessibility). Candidate SEO score
66 reflects its expected preview noindex; production indexability requires
separate HTTP verification after publishing.

The check covers the added shared stylesheet request supporting client
navigation. It does not establish conversion, ranking or AI-citation effects.
