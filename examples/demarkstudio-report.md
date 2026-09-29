# Website report card: https://demarkstudio.ca/

Prepared for: DeMark Studio (self-audit)  
Prepared by: DeMark Studio  
Date: 2026-09-29

**Overall grade: B (84/100), 8 of 8 areas checked**

| Area | Light | Score | Verdict |
|---|---|---:|---|
| Security | green | 98 | Well protected: security settings grade A+ (98/100). |
| Speed | red | 49 | Slow on phones: main content in 2.55 s, page busy for 625 ms (targets: 2.5 s and 200 ms). |
| Accessibility | amber | 70 | 2 problem(s) that make the site harder to use for some visitors (2 serious). |
| Privacy and consent | green | 98 | No tracking before consent; only low-risk services load (no consent banner). |
| Search engines (SEO) | green | 99 | In good shape for search engines: 7 page(s) checked, average 98.6/100. |
| Email deliverability | green | 90 | Email authentication is set up, with gaps in DMARC. |
| Social sharing | green | 84 | Shared links show a preview card, with small issues. |
| HTTP and hosting | green | 80 | HTTP/2, HTTP/3 advertised; 2 outdated or missing setting(s) to update. |

## Top fixes

1. **Cut down the scripts that run while the page loads** (Speed, high priority)  
   Why it matters: On a phone the page was too busy to respond for 625 ms while loading (target: under 200 ms), so taps and scrolling feel sluggish.  
   Who would fix it: your web developer

2. **Make keyboard navigation follow what is on screen** (Accessibility, high priority)  
   Why it matters: Visitors who use the keyboard instead of a mouse land on items they cannot see, so they lose their place.  
   Who would fix it: your web developer

3. **Stop others from sending email that pretends to be from your domain** (Email deliverability, medium priority)  
   Why it matters: The domain does not yet tell mail providers to reject fake email using your address, so scam messages that look like they come from you can still reach inboxes. Enforcing it also helps your real mail avoid spam folders.  
   Who would fix it: whoever manages your domain's DNS (often your web developer or IT provider)

## Details

<details><summary>Security: 98/100 (green)</summary>

Well protected: security settings grade A+ (98/100).

Tool: `security-headers-audit`

```text
HTTPS redirect: 10/10
TLS: 10/10
Strict-Transport-Security: 20/20
Content-Security-Policy: 20/20
Clickjacking (frame-ancestors / X-Frame-Options): 10/10
X-Content-Type-Options: 5/5
Referrer-Policy: 5/5
Permissions-Policy: 5/5
COOP / CORP: 3/5
  LOW: No Cross-Origin-Resource-Policy. Fix: Cross-Origin-Resource-Policy: same-origin
Cookies: 5/5
Server / version leakage: 5/5
```

</details>

<details><summary>Speed: 49/100 (red)</summary>

Slow on phones: main content in 2.55 s, page busy for 625 ms (targets: 2.5 s and 200 ms).

Tool: `web-vitals-lite`

```text
Profile: mobile (throttled CPU and network), 1 run(s), final URL https://demarkstudio.ca/en/
LCP (largest content shown): 2,548 ms (needs improvement, good <= 2,500 ms)
TBT (total blocking time): 625 ms (poor, good <= 200 ms)
CLS (layout shift): 0.000 (good, good <= 0.1)
FCP (first content): 2,492 ms
TTFB (server response): 374 ms
Page weight: 678.2 kB in 29 requests
Render-blocking resources in <head>: 2
LCP element: <img> section.apertura.bz-hero:nth-of-type(1) > div.contenedor > div.bz-hero-captura.sec-paralaje-vivo:nth-of-type(2) > a.sitio-foto.bz-captura-hero > img (https://demarkstudio.ca/static/img/portada/dashboard-1200.webp?v=6bbc2e3d)
Third-party domains: cloudflareinsights.com
```

</details>

<details><summary>Accessibility: 70/100 (amber)</summary>

2 problem(s) that make the site harder to use for some visitors (2 serious).

Tool: `a11y-audit`

```text
Page: https://demarkstudio.ca/en/; axe-core 4.13.0; keyboard sample 30 Tab stops
SERIOUS: focus-offscreen [2.4.7, 2.4.11] x10: Focused element is off-screen or has zero size. Fix: Bring focused items into view (scroll carousels to the focused slide, show skip links on :focus) or make hidden ones inert.
  - #herramientas > div > div:nth-of-type(2) > ul
  - #herramientas > div > div:nth-of-type(2) > ul > li:nth-of-type(1) > article > a
  - #herramientas > div > div:nth-of-type(2) > ul > li:nth-of-type(2) > article > a
SERIOUS: text-zoom-overflow [1.4.4, 1.4.10] x1: Page scrolls horizontally with text at 200%. Fix: Use relative widths (%, rem, max-width) and allow long words to wrap (overflow-wrap:anywhere).
  - #nav
```

</details>

<details><summary>Privacy and consent: 98/100 (green)</summary>

No tracking before consent; only low-risk services load (no consent banner).

Tool: `consent-tracker-scan`

```text
1 cookie(s) (0 third-party), 0 storage key(s), 1 third-party host(s); no consent banner
LOW: Cloudflare Web Analytics (cookieless analytics) loaded before consent. 1 request(s) to static.cloudflareinsights.com.
Third party: static.cloudflareinsights.com (cookieless_analytics, Cloudflare Web Analytics)
General information about privacy risk, not legal advice.
```

</details>

<details><summary>Search engines (SEO): 99/100 (green)</summary>

In good shape for search engines: 7 page(s) checked, average 98.6/100.

Tool: `site-seo-crawler`

```text
10 URL(s) requested, 7 page(s) scored, 0 error(s), 2 warning(s), 2 notice(s); robots.txt found; sitemap URLs 28
Crawl stopped at the page limit; other pages were not checked.
WARNING: title_length https://demarkstudio.ca/en/: Title is 82 characters (recommended 30-60)
WARNING: title_length https://demarkstudio.ca/en/for/salons: Title is 63 characters (recommended 30-60)
NOTICE: description_length https://demarkstudio.ca/en/for/salons: Meta description is 180 characters (recommended 70-160)
NOTICE: not_in_sitemap https://demarkstudio.ca/en/start: Reachable, indexable page that is not in the sitemap
```

</details>

<details><summary>Email deliverability: 90/100 (green)</summary>

Email authentication is set up, with gaps in DMARC.

Tool: `email-dns-check`

```text
MX: PASS, 1 MX host(s) (Google Workspace), all resolve
SPF: PASS, 1 record, 1/10 DNS lookups, 0/2 void lookups, ends with ~all
DMARC: WARN, p=none, aggregate reports on
  WARN: DMARC policy is p=none (monitoring only)
  Publish: _dmarc.demarkstudio.ca. TXT "v=DMARC1; p=quarantine; rua=mailto:hola@demarkstudio.ca"
DKIM: PASS, 1 key(s) found: google (2048-bit)
MTA-STS: INFO, Not published (optional)
TLS-RPT: INFO, Not published (optional)
BIMI: INFO, Not published (optional)
```

</details>

<details><summary>Social sharing: 84/100 (green)</summary>

Shared links show a preview card, with small issues.

Tool: `og-card-check`

```text
WARN: title is 82 chars; likely truncated above ~60
WARN: twitter title is 82 chars; X truncates around 70
Image og:image: HTTP 200 image/png 1200x630, 49255 bytes
Image twitter:image: HTTP 200 image/png 1200x630, 49255 bytes
Image favicon: HTTP 200 image/svg+xml ?, size unknown
Image apple-touch-icon: HTTP 200 image/png ?, 6088 bytes
```

</details>

<details><summary>HTTP and hosting: 80/100 (green)</summary>

HTTP/2, HTTP/3 advertised; 2 outdated or missing setting(s) to update.

Tool: `http-protocol-check`

```text
Host: demarkstudio.ca:443; HTTP/2, HTTP/3 advertised
TLS versions accepted: TLSv1.0, TLSv1.1, TLSv1.2, TLSv1.3
Certificate: 71 day(s) left, issuer CN=WE1,O=Google Trust Services,C=US
WARNING: tls-legacy: TLSv1.0 is accepted (deprecated by RFC 8996)
WARNING: tls-legacy: TLSv1.1 is accepted (deprecated by RFC 8996)
INFO: ipv6-not-tested: IPv6 not tested: this machine has no IPv6 route to the published AAAA address
```

</details>

## How this report was made

| Tool | Status | Exit code | Time |
|---|---|---|---:|
| security-headers-audit | ok | 0 | 3.3 s |
| web-vitals-lite | ok | 0 | 8.5 s |
| a11y-audit | ok | 0 | 13.7 s |
| consent-tracker-scan | ok | 0 | 4.9 s |
| site-seo-crawler | ok | 0 | 12.4 s |
| og-card-check | ok | 0 | 3.4 s |
| email-dns-check | ok | 0 | 0.9 s |
| http-protocol-check | ok | 0 | 6.9 s |

Grade weights: Security 20, Speed 15, Accessibility 15, Privacy and consent 15, Search engines (SEO) 15, Email deliverability 10, Social sharing 5, HTTP and hosting 5. Areas that were not checked are left out and the remaining weights are scaled up. A >= 90, B >= 80, C >= 70, D >= 60, F below. Lights: green >= 80, amber >= 50, red below.

Automated checks catch many common problems, not all of them. The privacy notes are general information, not legal advice.
