import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Canned output of each tool for an invented site, in the shapes the real tools print.
CANNED = {
    "security-headers-audit": [{
        "url": "https://www.example.com", "final_url": "https://www.example.com/", "status": 200,
        "redirects": [], "score": 72, "grade": "B", "error": None,
        "checks": [
            {"check": "hsts", "title": "Strict-Transport-Security", "points": 0, "max_points": 20,
             "findings": [{"severity": "high", "message": "No Strict-Transport-Security header.",
                           "fix": "Strict-Transport-Security: max-age=63072000; includeSubDomains"}]},
            {"check": "csp", "title": "Content-Security-Policy", "points": 20, "max_points": 20,
             "findings": [{"severity": "pass", "message": "CSP is strict.", "fix": None}]},
            {"check": "cross-origin", "title": "COOP / CORP", "points": 3, "max_points": 5,
             "findings": [{"severity": "low", "message": "No Cross-Origin-Resource-Policy.",
                           "fix": "Cross-Origin-Resource-Policy: same-origin"}]},
        ],
    }],
    "web-vitals-lite": {
        "tool": "web-vitals-lite", "results": [{
            "url": "https://www.example.com/", "profile": "mobile", "runs_ok": 1, "runs_failed": 0,
            "errors": [], "final_url": "https://www.example.com/",
            "median": {"ttfb_ms": 300.0, "fcp_ms": 1800.0, "lcp_ms": 3200.0, "cls": 0.02,
                       "tbt_ms": 150.0, "total_bytes": 900000, "requests": 20, "render_blocking": 1},
            "details": {"lcp_element": {"tag": "img", "selector": "main > img.hero",
                                        "url": "https://www.example.com/hero.jpg"},
                        "third_party_domains": {"example.net": 1200}},
        }],
    },
    "a11y-audit": {
        "tool": "a11y-audit", "axe_version": "4.13.0",
        "pages": [{
            "url": "https://www.example.com/", "final_url": "https://www.example.com/", "error": None,
            "focus_order": [{"selector": "a.skip"}],
            "violations": [
                {"id": "color-contrast", "impact": "serious", "wcag": ["1.4.3"], "count": 3,
                 "help": "Elements must meet minimum color contrast ratio thresholds",
                 "fix": "Darken the text.", "nodes": [{"selector": "p.muted"}]},
                {"id": "region", "impact": "moderate", "wcag": [], "count": 1,
                 "help": "All page content should be contained by landmarks",
                 "fix": "Use landmarks.", "nodes": [{"selector": "#promo"}]},
            ],
            "check_errors": [],
        }],
    },
    "consent-tracker-scan": {
        "tool": "consent-tracker-scan",
        "consent_banner": {"detected": True, "cmp": "Cookiebot"},
        "summary": {"high": 1, "medium": 0, "low": 1, "pages_scanned": 1, "cookies": 2,
                    "third_party_cookies": 1, "storage_keys": 0, "third_party_hosts": 2,
                    "unknown_third_party_hosts": 0, "trackers": ["Google Analytics"]},
        "findings": [
            {"severity": "high", "kind": "request",
             "title": "Google Analytics (analytics) loaded before consent",
             "detail": "3 request(s) to www.google-analytics.com."},
            {"severity": "low", "kind": "request", "title": "Google Fonts (cdn fonts) loaded before consent",
             "detail": "2 request(s) to fonts.gstatic.com."},
        ],
        "third_party_hosts": [{"host": "www.google-analytics.com", "category": "analytics",
                               "tracker": "Google Analytics"}],
        "pages": [{"url": "https://www.example.com/", "error": None}],
    },
    "site-seo-crawler": {
        "tool": "site-seo-crawler",
        "summary": {"urls_requested": 10, "pages_scored": 8, "average_score": 91.5,
                    "issues": {"error": 1, "warning": 1, "notice": 0}, "robots_txt": "found",
                    "sitemap_urls": 8, "truncated": True, "notes": []},
        "issues": [
            {"type": "broken_link", "severity": "error", "url": "https://www.example.com/old-menu",
             "message": "HTTP 404", "count": 1, "related": ["https://www.example.com/"]},
            {"type": "title_length", "severity": "warning", "url": "https://www.example.com/about",
             "message": "Title is 72 characters", "count": 1, "related": []},
        ],
    },
    "og-card-check": [{
        "url": "https://www.example.com", "status": 200,
        "findings": [
            {"level": "error", "code": "missing-tag", "message": "og:image is missing"},
            {"level": "warn", "code": "title-long", "message": "title is 72 chars; likely truncated above ~60"},
            {"level": "warn", "code": "missing-canonical", "message": "no <link rel=canonical>"},
            {"level": "info", "code": "missing-tag", "message": "og:site_name is missing"},
        ],
        "images": {},
    }],
    "email-dns-check": {
        "tool": "email-dns-check", "status": "warn",
        "domains": [{"domain": "example.com", "status": "warn", "checks": [
            {"name": "MX", "status": "pass", "summary": "1 MX host(s), all resolve", "findings": []},
            {"name": "SPF", "status": "pass", "summary": "1 record, ends with ~all", "findings": []},
            {"name": "DMARC", "status": "warn", "summary": "p=none, aggregate reports on",
             "findings": [{"severity": "warn", "title": "DMARC policy is p=none (monitoring only)",
                           "record": "_dmarc.example.com. TXT \"v=DMARC1; p=quarantine\""}]},
            {"name": "DKIM", "status": "pass", "summary": "1 key(s) found", "findings": []},
            {"name": "BIMI", "status": "info", "summary": "Not published (optional)", "findings": []},
        ]}],
    },
    "http-protocol-check": {
        "tool": "http-protocol-check",
        "hosts": [{
            "host": "www.example.com", "port": 443, "error": None,
            "checks": {"alpn": {"h2": True}, "http3": {"advertised": False},
                       "tls_versions": [{"version": "TLSv1.0", "status": "accepted"},
                                        {"version": "TLSv1.1", "status": "refused"},
                                        {"version": "TLSv1.2", "status": "accepted"},
                                        {"version": "TLSv1.3", "status": "accepted"}],
                       "certificate": {"days_left": 60, "issuer": "CN=Example CA"}},
            "findings": [
                {"level": "warning", "code": "tls-legacy", "message": "TLSv1.0 is accepted"},
                {"level": "warning", "code": "hsts-missing", "message": "no Strict-Transport-Security header"},
                {"level": "info", "code": "no-h3-advert", "message": "HTTP/3 is not advertised"},
            ],
        }],
    },
}


@pytest.fixture
def canned():
    return copy.deepcopy(CANNED)
