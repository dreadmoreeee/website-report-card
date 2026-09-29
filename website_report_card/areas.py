"""Turn each tool's JSON into a report card area with a score, a verdict and plain-language fixes."""

from __future__ import annotations

import dataclasses

# key, title, weight in the overall grade (sums to 100)
AREAS: list[tuple[str, str, int]] = [
    ("security", "Security", 20),
    ("speed", "Speed", 15),
    ("accessibility", "Accessibility", 15),
    ("privacy", "Privacy and consent", 15),
    ("seo", "Search engines (SEO)", 15),
    ("email", "Email deliverability", 10),
    ("social", "Social sharing", 5),
    ("http", "HTTP and hosting", 5),
]
TITLES = {k: t for k, t, _ in AREAS}
WEIGHTS = {k: w for k, _, w in AREAS}

GREEN, AMBER, RED = "green", "amber", "red"
SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

WEB_DEV = "your web developer"
HOST = "your web host or web developer"
DNS = "whoever manages your domain's DNS (often your web developer or IT provider)"
CONTENT = "whoever edits the website's content"
MARKETING = "your web developer, or whoever added the marketing and analytics tags"


class NotChecked(Exception):
    """The tool ran but its output does not allow a verdict (for example, the site was unreachable)."""


@dataclasses.dataclass
class Issue:
    area: str
    concern: str        # issues about the same thing from two tools share this key
    severity: str       # high, medium, low
    title: str          # what to do, plain language
    why: str            # why it matters to the business
    who: str            # who would fix it
    technical: str = ""

    def rank(self) -> tuple:
        return (SEVERITY_RANK[self.severity], WEIGHTS.get(self.area, 0))


@dataclasses.dataclass
class Area:
    key: str
    tool: str
    checked: bool = False
    score: int | None = None
    verdict: str = ""
    reason: str = ""                    # why it was not checked
    details: list[str] = dataclasses.field(default_factory=list)
    issues: list[Issue] = dataclasses.field(default_factory=list)

    @property
    def title(self) -> str:
        return TITLES[self.key]

    @property
    def weight(self) -> int:
        return WEIGHTS[self.key]

    @property
    def light(self) -> str | None:
        return light_for(self.score) if self.checked else None


def light_for(score: int) -> str:
    if score >= 80:
        return GREEN
    if score >= 50:
        return AMBER
    return RED


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def _pick(light: str, green: str, amber: str, red: str) -> str:
    return {GREEN: green, AMBER: amber, RED: red}[light]


def _first(data, what: str):
    if isinstance(data, list):
        if not data:
            raise NotChecked(f"the tool returned no {what}")
        return data[0]
    if isinstance(data, dict):
        return data
    raise NotChecked("unexpected JSON shape")


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _sev(value: str) -> str:
    return {"critical": "high", "high": "high", "error": "high", "fail": "high",
            "serious": "high", "medium": "medium", "warning": "medium", "warn": "medium",
            "moderate": "medium"}.get(value, "low")


# ---------------------------------------------------------------- security

_SEC = {
    "https-redirect": ("https-redirect", "Send every visitor to the secure (https) version of the site",
                       "Visitors who type the address without https can land on an unprotected page "
                       "that others on the same Wi-Fi can read or change.", HOST),
    "tls": ("certificate", "Fix or renew the site's security certificate",
            "When the certificate is invalid or expires, browsers show a full-page warning and "
            "most visitors leave.", HOST),
    "hsts": ("hsts", "Tell browsers to always use the secure connection",
             "Without this setting, a visitor's first request can be intercepted and redirected "
             "on public Wi-Fi.", HOST),
    "csp": ("csp", "Add a content security policy (a list of what the site may load)",
            "It limits the damage if someone manages to slip harmful code into a page.", WEB_DEV),
    "frame": ("frame", "Stop other websites from showing your pages inside theirs",
              "It blocks tricks where your page is hidden under another site to steal clicks.",
              WEB_DEV),
    "cookies": ("cookies", "Protect the site's cookies",
                "Login and session cookies without protective settings are easier to steal.",
                WEB_DEV),
    "leakage": ("leakage", "Hide the software version numbers the server reveals",
                "Version numbers tell attackers which known weaknesses to try.", HOST),
}
_SEC_EXTRA = ("security-extras", "Add the remaining standard security settings",
              "Each one is a single server setting that closes a small gap.", WEB_DEV)


def security(data) -> Area:
    r = _first(data, "result")
    if r.get("error"):
        raise NotChecked(f"the site could not be reached: {r['error']}")
    if r.get("score") is None:
        raise NotChecked("no score in the tool output")
    area = Area("security", "security-headers-audit", checked=True, score=_clamp(r["score"]))
    grade = r.get("grade", "?")
    area.verdict = _pick(light_for(area.score),
                         f"Well protected: security settings grade {grade} ({area.score}/100).",
                         f"Some protections are missing: grade {grade} ({area.score}/100).",
                         f"Important protections are missing: grade {grade} ({area.score}/100).")
    for c in r.get("checks") or []:
        area.details.append(f"{c.get('title')}: {c.get('points'):g}/{c.get('max_points')}")
        serious = [f for f in c.get("findings") or [] if f.get("severity") not in ("pass", "info")]
        for f in serious:
            fix = f" Fix: {f['fix']}" if f.get("fix") else ""
            area.details.append(f"  {f['severity'].upper()}: {f.get('message')}{fix}")
        if serious:
            worst = max(serious, key=lambda f: SEVERITY_RANK[_sev(f["severity"])])
            concern, title, why, who = _SEC.get(c.get("check"), _SEC_EXTRA)
            area.issues.append(Issue("security", concern, _sev(worst["severity"]), title, why, who,
                                     worst.get("message", "")))
    return area


# ---------------------------------------------------------------- speed

# (good, poor) thresholds, as published for Core Web Vitals; TBT uses the lab thresholds.
_THRESHOLDS = {"lcp_ms": (2500, 4000), "tbt_ms": (200, 600), "cls": (0.1, 0.25)}
_SPEED_WEIGHTS = {"lcp_ms": 40, "tbt_ms": 30, "cls": 30}


def metric_score(value: float, good: float, poor: float) -> float:
    """100 up to good, 50 at poor, 0 at twice poor, linear in between."""
    if value <= good:
        return 100.0
    if value <= poor:
        return 100.0 - 50.0 * (value - good) / (poor - good)
    return max(0.0, 50.0 - 50.0 * (value - poor) / poor)


def _band(key: str, value: float) -> str:
    good, poor = _THRESHOLDS[key]
    return "good" if value <= good else ("needs improvement" if value <= poor else "poor")


def speed(data) -> Area:
    results = (data or {}).get("results") if isinstance(data, dict) else None
    if not results:
        raise NotChecked("no measurement in the tool output")
    r = next((x for x in results if x.get("profile") == "mobile"), results[0])
    med = r.get("median") or {}
    if not r.get("runs_ok") or med.get("lcp_ms") is None:
        errs = r.get("errors") or []
        raise NotChecked("the page could not be measured" + (f": {errs[0]}" if errs else ""))
    parts = {k: metric_score(med[k], *_THRESHOLDS[k]) for k in _SPEED_WEIGHTS
             if med.get(k) is not None}
    total = sum(_SPEED_WEIGHTS[k] for k in parts)
    value = sum(parts[k] * _SPEED_WEIGHTS[k] for k in parts) / total
    # A page passes Core Web Vitals only when every metric is good, so the light follows the worst.
    bands = {_band(k, med[k]) for k in parts}
    if "poor" in bands:
        value = min(value, 49)
    elif "needs improvement" in bands:
        value = min(value, 79)
    area = Area("speed", "web-vitals-lite", checked=True, score=_clamp(value))
    lcp_s = f"{med['lcp_ms'] / 1000:.2f}"
    tbt = med.get("tbt_ms")
    cls = med.get("cls")
    busy = f", page busy for {tbt:,.0f} ms" if tbt is not None else ""
    area.verdict = _pick(light_for(area.score),
                         f"Loads quickly on a phone: main content in {lcp_s} s{busy}.",
                         f"A bit slow on phones: main content in {lcp_s} s{busy} "
                         f"(targets: 2.5 s and 200 ms).",
                         f"Slow on phones: main content in {lcp_s} s{busy} "
                         f"(targets: 2.5 s and 200 ms).")
    profile = r.get("profile", "mobile")
    area.details.append(f"Profile: {profile} (throttled CPU and network), "
                        f"{r.get('runs_ok')} run(s), final URL {r.get('final_url') or r.get('url')}")
    area.details.append(f"LCP (largest content shown): {med['lcp_ms']:,.0f} ms "
                        f"({_band('lcp_ms', med['lcp_ms'])}, good <= 2,500 ms)")
    if tbt is not None:
        area.details.append(f"TBT (total blocking time): {tbt:,.0f} ms "
                            f"({_band('tbt_ms', tbt)}, good <= 200 ms)")
    if cls is not None:
        area.details.append(f"CLS (layout shift): {cls:.3f} ({_band('cls', cls)}, good <= 0.1)")
    for key, label in (("fcp_ms", "FCP (first content)"), ("ttfb_ms", "TTFB (server response)")):
        if med.get(key) is not None:
            area.details.append(f"{label}: {med[key]:,.0f} ms")
    size = med.get("total_bytes")
    if size is not None:
        area.details.append(f"Page weight: {size / 1000:,.1f} kB in {med.get('requests', '?')} requests")
    if med.get("render_blocking") is not None:
        area.details.append(f"Render-blocking resources in <head>: {med['render_blocking']}")
    det = r.get("details") or {}
    lcp_el = det.get("lcp_element") or {}
    if lcp_el.get("selector"):
        area.details.append(f"LCP element: <{lcp_el.get('tag')}> {lcp_el['selector']}"
                            + (f" ({lcp_el['url']})" if lcp_el.get("url") else ""))
    third = det.get("third_party_domains") or {}
    if third:
        area.details.append("Third-party domains: " + ", ".join(sorted(third)))

    if _band("lcp_ms", med["lcp_ms"]) != "good":
        why = (f"On a mid-range phone with a slow connection the main content took {lcp_s} s "
               "to appear; Google recommends under 2.5 s, and slow pages lose visitors and rank lower.")
        if lcp_el.get("tag") == "img":
            why += " The slowest item is the large image at the top of the page; a smaller, compressed version usually fixes it."
        area.issues.append(Issue("speed", "lcp", "high" if _band("lcp_ms", med["lcp_ms"]) == "poor"
                                 else "medium", "Make the main content appear faster on phones",
                                 why, WEB_DEV, f"LCP {med['lcp_ms']:,.0f} ms"))
    if tbt is not None and _band("tbt_ms", tbt) != "good":
        area.issues.append(Issue(
            "speed", "tbt", "high" if _band("tbt_ms", tbt) == "poor" else "medium",
            "Cut down the scripts that run while the page loads",
            f"On a phone the page was too busy to respond for {tbt:,.0f} ms while loading "
            "(target: under 200 ms), so taps and scrolling feel sluggish.", WEB_DEV,
            f"TBT {tbt:,.0f} ms"))
    if cls is not None and _band("cls", cls) != "good":
        area.issues.append(Issue(
            "speed", "cls", "high" if _band("cls", cls) == "poor" else "medium",
            "Stop the page from jumping around while it loads",
            "Content that moves while loading makes visitors lose their place or tap the wrong thing.",
            WEB_DEV, f"CLS {cls:.3f}"))
    if size is not None and size > 3_000_000:
        area.issues.append(Issue(
            "speed", "weight", "medium", "Make the page lighter",
            f"The page downloads {size / 1_000_000:.1f} MB; on mobile data that is slow and uses "
            "up visitors' data plans.", WEB_DEV, f"{size:,} bytes"))
    return area


# ---------------------------------------------------------------- accessibility

_A11Y_POINTS = {"critical": 25, "serious": 15, "moderate": 7, "minor": 3}
_A11Y_WHY = ("People who use a keyboard, a screen reader or larger text have trouble with this "
             "part of the site.")
_ZOOM = ("Keep the layout working when visitors enlarge the text",
         "People with low vision enlarge the text; at 200% part of this page no longer fits "
         "and has to be scrolled sideways or is cut off.")
_MOTION = ("Respect visitors who ask for less motion",
           "Some people get dizzy from animation and switch it off in their device settings; "
           "the site keeps animating anyway.")
_A11Y = {
    "color-contrast": ("Make pale or low-contrast text easier to read",
                       "Faint text is hard to read for many visitors, especially older people and "
                       "anyone using a phone outdoors."),
    "image-alt": ("Describe images for visitors who cannot see them",
                  "Screen readers read the description aloud; without one, blind visitors miss "
                  "the content."),
    "label": ("Label every form field",
              "Without labels, screen reader users do not know what to type in each box."),
    "link-name": ("Give every link readable text",
                  "Links without text are announced only as 'link', so screen reader users "
                  "cannot tell where they go."),
    "button-name": ("Give every button readable text",
                    "Buttons without text are announced only as 'button', so screen reader users "
                    "cannot tell what they do."),
    "html-has-lang": ("Declare the language of each page",
                      "Screen readers use it to pronounce the text correctly."),
    "document-title": ("Give every page a title",
                       "The title is the first thing a screen reader announces."),
    "focus-offscreen": ("Make keyboard navigation follow what is on screen",
                        "Visitors who use the keyboard instead of a mouse land on items they "
                        "cannot see, so they lose their place."),
    "focus-not-visible": ("Show where the keyboard focus is",
                          "Keyboard users cannot see which link or button is selected."),
    "focus-trap": ("Let keyboard users move past every part of the page",
                   "Keyboard users get stuck and cannot reach the rest of the page."),
    "focus-order-jump": ("Make keyboard navigation follow the reading order",
                         "Keyboard users jump around the page unpredictably."),
    "text-zoom-overflow": _ZOOM, "text-zoom-clipped": _ZOOM, "text-zoom-offscreen": _ZOOM,
    "motion-animation-running": _MOTION, "motion-transition": _MOTION,
    "motion-smooth-scroll": _MOTION,
    "region": ("Put all content inside the page's main sections",
               "Screen reader users jump from section to section; content outside them is easy "
               "to miss."),
}


def accessibility(data) -> Area:
    if not isinstance(data, dict) or not data.get("pages"):
        raise NotChecked("no page in the tool output")
    page = data["pages"][0]
    if page.get("error"):
        raise NotChecked(f"the page could not be audited: {page['error']}")
    violations = page.get("violations") or []
    lost = sum(_A11Y_POINTS.get(v.get("impact"), 3) for v in violations)
    area = Area("accessibility", "a11y-audit", checked=True, score=_clamp(100 - lost))
    counts = {i: sum(1 for v in violations if v.get("impact") == i) for i in _A11Y_POINTS}
    summary = ", ".join(f"{n} {i}" for i, n in counts.items() if n)
    if not violations:
        area.verdict = ("No problems found by the automated checks "
                        "(they catch only part of all accessibility issues).")
    else:
        area.verdict = (f"{len(violations)} problem(s) that make the site harder to use for some "
                        f"visitors ({summary}).")
    tabs = [f for f in page.get("focus_order") or [] if f.get("selector") != "(document)"]
    area.details.append(f"Page: {page.get('final_url') or page.get('url')}; axe-core "
                        f"{data.get('axe_version') or '?'}; keyboard sample {len(tabs)} Tab stops")
    for v in violations:
        wcag = ", ".join(v.get("wcag") or []) or "best practice"
        area.details.append(f"{(v.get('impact') or '?').upper()}: {v.get('id')} [{wcag}] "
                            f"x{v.get('count', 0)}: {v.get('help')}. Fix: {v.get('fix')}")
        for n in (v.get("nodes") or [])[:3]:
            area.details.append(f"  - {n.get('selector')}")
    for err in page.get("check_errors") or []:
        area.details.append(f"Check not completed: {err.get('check')}: {err.get('error')}")
    for v in violations:
        title, why = _A11Y.get(v.get("id"), (f"Fix an accessibility problem: {v.get('help')}",
                                              _A11Y_WHY))
        area.issues.append(Issue("accessibility", "a11y:" + title, _sev(v.get("impact", "")),
                                 title, why, WEB_DEV, f"{v.get('id')}: {v.get('help')}"))
    return area


# ---------------------------------------------------------------- privacy

def privacy(data) -> Area:
    if not isinstance(data, dict) or "summary" not in data:
        raise NotChecked("no summary in the tool output")
    s = data["summary"]
    if not s.get("pages_scanned"):
        errors = [p.get("error") for p in data.get("pages") or [] if p.get("error")]
        raise NotChecked("the page could not be scanned" + (f": {errors[0]}" if errors else ""))
    high, medium, low = s.get("high", 0), s.get("medium", 0), s.get("low", 0)
    area = Area("privacy", "consent-tracker-scan", checked=True,
                score=_clamp(100 - 30 * high - 10 * medium - 2 * low))
    banner = data.get("consent_banner") or {}
    banner_txt = f"consent banner: {banner.get('cmp')}" if banner.get("detected") else "no consent banner"
    trackers = s.get("trackers") or []
    findings = data.get("findings") or []
    if high:
        area.verdict = f"Tracking starts before visitors agree ({', '.join(trackers) or 'see details'})."
    elif medium:
        area.verdict = "Third-party services load before consent; check whether they need it."
    elif low:
        area.verdict = f"No tracking before consent; only low-risk services load ({banner_txt})."
    else:
        area.verdict = f"No tracking and no third-party services before consent ({banner_txt})."
    area.details.append(f"{s.get('cookies', 0)} cookie(s) ({s.get('third_party_cookies', 0)} third-party), "
                        f"{s.get('storage_keys', 0)} storage key(s), "
                        f"{s.get('third_party_hosts', 0)} third-party host(s); {banner_txt}")
    for f in findings:
        area.details.append(f"{f.get('severity', '').upper()}: {f.get('title')}. {f.get('detail', '')}".rstrip())
    for h in data.get("third_party_hosts") or []:
        area.details.append(f"Third party: {h.get('host')} ({h.get('category')}"
                            + (f", {h['tracker']}" if h.get("tracker") else "") + ")")
    area.details.append("General information about privacy risk, not legal advice.")
    if high:
        names = ", ".join(trackers) or "Tracking tools"
        area.issues.append(Issue(
            "privacy", "consent-trackers", "high",
            "Stop tracking tools from running before visitors agree",
            f"{names} load as soon as someone opens the page, before any consent. Canadian "
            "privacy law (PIPEDA, and Quebec's Law 25) expects consent for this kind of "
            "tracking. General information, not legal advice.", MARKETING,
            "; ".join(f["title"] for f in findings if f.get("severity") == "high")))
    if medium:
        titles = [f["title"] for f in findings if f.get("severity") == "medium"]
        area.issues.append(Issue(
            "privacy", "consent-unknown", "medium",
            "Check the outside services that load before consent",
            f"{len(titles)} outside service(s) load on the first visit; if they track visitors "
            "they may need consent first.", MARKETING, "; ".join(titles)))
    return area


# ---------------------------------------------------------------- seo

_SEO = {
    "broken_link": ("broken-links", "Fix broken links",
                    "{n} link(s) lead to error pages: visitors hit a dead end and search engines "
                    "see a site that looks unmaintained.", CONTENT),
    "redirect_loop": ("redirect-loop", "Fix links that go round in circles",
                      "The page never loads for visitors or search engines.", WEB_DEV),
    "redirect_chain": ("redirect-chain", "Point links straight at their final address",
                       "Each extra hop slows the page down.", WEB_DEV),
    "title_missing": ("titles", "Give every page a title",
                      "The title is the blue link people click in Google results.", CONTENT),
    "title_duplicate": ("titles", "Give each page its own title",
                        "Pages with the same title compete with each other in search results.",
                        CONTENT),
    "title_length": ("titles", "Keep page titles between 30 and 60 characters",
                     "Longer titles are cut off in search results.", CONTENT),
    "description_missing": ("descriptions", "Write a short summary for each page",
                            "Google often shows it under the title; without one it picks "
                            "random text from the page.", CONTENT),
    "description_duplicate": ("descriptions", "Give each page its own summary",
                              "Identical summaries make pages look interchangeable in search "
                              "results.", CONTENT),
    "description_length": ("descriptions", "Keep page summaries between 70 and 160 characters",
                           "Longer summaries are cut off in search results.", CONTENT),
    "canonical_missing": ("canonical", "Tell search engines the main address of each page",
                          "It stops the same page from being counted twice under different "
                          "addresses.", WEB_DEV),
    "canonical_mismatch": ("canonical", "Check which address each page tells search engines to use",
                           "Pages that point to another address may drop out of search results.",
                           WEB_DEV),
    "noindex": ("noindex", "Check the pages that are hidden from Google",
                "{n} page(s) ask search engines not to list them; make sure that is intended.",
                WEB_DEV),
    "img_missing_alt": ("img-alt", "Describe the images",
                        "Search engines and screen readers rely on image descriptions.", CONTENT),
    "h1_missing": ("h1", "Give each page one main heading",
                   "The main heading tells visitors and search engines what the page is about.",
                   CONTENT),
    "h1_multiple": ("h1", "Give each page one main heading",
                    "The main heading tells visitors and search engines what the page is about.",
                    CONTENT),
    "jsonld_invalid": ("jsonld", "Fix the structured data",
                       "Broken structured data stops Google from showing extras such as "
                       "business hours or ratings.", WEB_DEV),
    "mixed_content": ("mixed-content", "Load every file over the secure connection",
                      "Browsers block insecure files on secure pages, which can break images or "
                      "features.", WEB_DEV),
}
_HREFLANG = ("hreflang", "Fix the links between language versions",
             "Search engines use them to show French speakers the French page and English "
             "speakers the English one.", WEB_DEV)
_SITEMAP = ("sitemap", "Keep the sitemap in step with the site's links",
            "The sitemap is the list of pages you give to Google; pages missing from it, or "
            "listed but not linked, are found late or not at all.", WEB_DEV)
_SEO_SEV = {"error": "high", "warning": "medium", "notice": "low"}
# Cosmetic warnings: worth doing, never ahead of problems that cost visitors.
_SEO_LOW = {"title_length", "description_length", "redirect_chain", "h1_multiple"}


def seo(data) -> Area:
    if not isinstance(data, dict) or "summary" not in data:
        raise NotChecked("no summary in the tool output")
    s = data["summary"]
    if not s.get("pages_scored") or s.get("average_score") is None:
        notes = s.get("notes") or []
        raise NotChecked("no page could be crawled" + (f": {notes[0]}" if notes else ""))
    area = Area("seo", "site-seo-crawler", checked=True, score=_clamp(s["average_score"]))
    iss = s.get("issues") or {}
    counts = f"{iss.get('error', 0)} error(s), {iss.get('warning', 0)} warning(s), {iss.get('notice', 0)} notice(s)"
    area.verdict = _pick(light_for(area.score),
                         f"In good shape for search engines: {s['pages_scored']} page(s) checked, "
                         f"average {s['average_score']:g}/100.",
                         f"Some search engine issues: {s['pages_scored']} page(s) checked, "
                         f"average {s['average_score']:g}/100.",
                         f"Search engines see serious problems: {s['pages_scored']} page(s) checked, "
                         f"average {s['average_score']:g}/100.")
    area.details.append(f"{s.get('urls_requested', '?')} URL(s) requested, {s['pages_scored']} page(s) scored, "
                        f"{counts}; robots.txt {s.get('robots_txt', '?')}; "
                        f"sitemap URLs {s.get('sitemap_urls', 0)}")
    if s.get("truncated"):
        area.details.append("Crawl stopped at the page limit; other pages were not checked.")
    issues = data.get("issues") or []
    for i in issues[:40]:
        related = i.get("related") or []
        via = f" (linked from {related[0]})" if related else ""
        area.details.append(f"{i.get('severity', '').upper()}: {i.get('type')} {i.get('url')}: "
                            f"{i.get('message', '')}{via}")
    if len(issues) > 40:
        area.details.append(f"... {len(issues) - 40} more issue(s) in the raw JSON")
    by_type: dict[str, list[dict]] = {}
    for i in issues:
        by_type.setdefault(i.get("type", ""), []).append(i)
    for kind, group in by_type.items():
        if kind.startswith("hreflang"):
            concern, title, why, who = _HREFLANG
        elif kind in ("sitemap_not_linked", "not_in_sitemap"):
            concern, title, why, who = _SITEMAP
        elif kind in _SEO:
            concern, title, why, who = _SEO[kind]
        else:
            concern, title, why, who = (kind, f"Fix: {kind.replace('_', ' ')}",
                                        "It affects how search engines read the site.", WEB_DEV)
        sev = max((_SEO_SEV.get(i.get("severity"), "low") for i in group), key=SEVERITY_RANK.get)
        if kind in _SEO_LOW:
            sev = "low"
        area.issues.append(Issue("seo", "seo:" + concern, sev, title,
                                 why.replace("{n}", str(len(group))), who,
                                 f"{kind} x{len(group)}: {group[0].get('url')} {group[0].get('message', '')}"))
    return area


# ---------------------------------------------------------------- social

def social(data) -> Area:
    r = _first(data, "page")
    findings = r.get("findings") or []
    codes = {f.get("code") for f in findings}
    if not r.get("status") or r.get("status", 0) >= 400 or codes & {"fetch-failed", "not-html"}:
        msg = next((f["message"] for f in findings if f.get("level") == "error"), "no response")
        raise NotChecked(f"the page could not be read: {msg}")
    errors = [f for f in findings if f.get("level") == "error"]
    warns = [f for f in findings if f.get("level") == "warn"]
    area = Area("social", "og-card-check", checked=True,
                score=_clamp(100 - 25 * len(errors) - 8 * len(warns)))
    if errors:
        area.verdict = f"Shared links will look bare or broken: {errors[0]['message']}."
    elif warns:
        area.verdict = "Shared links show a preview card, with small issues."
    else:
        area.verdict = "Shared links show a complete preview card."
    for f in errors + warns + [f for f in findings if f.get("level") == "info"]:
        area.details.append(f"{f.get('level', '').upper()}: {f.get('message')}")
    for k, v in (r.get("images") or {}).items():
        dim = f"{v['width']}x{v['height']}" if v.get("width") else "?"
        size = f"{v['bytes']} bytes" if v.get("bytes") is not None else "size unknown"
        area.details.append(f"Image {k}: HTTP {v.get('status')} {v.get('content_type') or '-'} "
                            f"{dim}, {size}")
    for f in errors + warns:
        code, msg = f.get("code", ""), f.get("message", "")
        sev = _sev(f.get("level", ""))
        if "og:image" in msg or code.startswith("image") or code == "relative-image":
            area.issues.append(Issue("social", "og-image", sev, "Add a working preview image for shared links",
                                     "When someone shares the site on Facebook, LinkedIn or in a "
                                     "message, the link appears without a picture and gets fewer "
                                     "clicks.", WEB_DEV, msg))
        elif code in ("title-long", "twitter-title-long", "description-long"):
            area.issues.append(Issue("social", "og-length", "low",
                                     "Shorten the title shown when the site is shared",
                                     "Social networks cut long titles off after about 60 "
                                     "characters, so the end of the message is lost.", CONTENT, msg))
        elif code == "missing-canonical":
            continue
        else:
            area.issues.append(Issue("social", "og-tags", sev,
                                     "Complete the tags that control how shared links look",
                                     "They set the title, text and picture people see when the "
                                     "site is shared.", WEB_DEV, msg))
    return area


# ---------------------------------------------------------------- email

_EMAIL = {
    "MX": ("Fix the domain's incoming mail settings",
           "Mail sent to your address may bounce or get lost."),
    "SPF": ("Fix the list of servers allowed to send your email",
            "Without a correct list, your own emails are more likely to land in spam, and others "
            "can send mail pretending to be you."),
    "DMARC": ("Stop others from sending email that pretends to be from your domain",
              "The domain does not yet tell mail providers to reject fake email using your "
              "address, so scam messages that look like they come from you can still reach "
              "inboxes. Enforcing it also helps your real mail avoid spam folders."),
    "DKIM": ("Turn on email signing with your email provider",
             "Signed email is trusted more by Gmail and Outlook and is less likely to go to spam."),
}


def email(data) -> Area:
    if not isinstance(data, dict) or not data.get("domains"):
        raise NotChecked("no domain in the tool output")
    d = data["domains"][0]
    checks = d.get("checks") or []
    if not checks:
        raise NotChecked(d.get("error") or "no checks in the tool output")
    fails = [c for c in checks if c.get("status") == "fail"]
    warns = [c for c in checks if c.get("status") == "warn"]
    area = Area("email", "email-dns-check", checked=True,
                score=_clamp(100 - 30 * len(fails) - 10 * len(warns)))
    if fails:
        area.verdict = (f"Email from {d.get('domain')} can be faked or lost: "
                        f"{', '.join(c['name'] for c in fails)} failed.")
    elif warns:
        area.verdict = ("Email authentication is set up, with gaps in "
                        f"{_join([c['name'] for c in warns])}.")
    else:
        area.verdict = "Email authentication (SPF, DKIM, DMARC) is set up correctly."
    for c in checks:
        area.details.append(f"{c.get('name')}: {c.get('status', '').upper()}, {c.get('summary', '')}")
        for f in c.get("findings") or []:
            if f.get("severity") in ("fail", "warn"):
                area.details.append(f"  {f['severity'].upper()}: {f.get('title')}")
                if f.get("record"):
                    area.details.append(f"  Publish: {f['record']}")
    for c in fails + warns:
        title, why = _EMAIL.get(c.get("name"), (f"Fix the {c.get('name')} email record",
                                                "It helps your email reach inboxes."))
        who = DNS if c.get("name") != "DKIM" else "your email provider's admin panel, then " + DNS
        area.issues.append(Issue("email", "email:" + str(c.get("name")), _sev(c.get("status", "")),
                                 title, why, who, f"{c.get('name')}: {c.get('summary', '')}"))
    return area


# ---------------------------------------------------------------- http

_HTTP = {
    "tls-legacy": ("tls-legacy", "Switch off the old encryption versions (TLS 1.0 and 1.1)",
                   "They are retired standards with known weaknesses. Current browsers no longer "
                   "use them, so switching them off does not lock out real visitors.",
                   "your web host (often one setting in the hosting or CDN dashboard)"),
    "cert-expired": _SEC["tls"], "cert-expiring": _SEC["tls"], "cert-verify": _SEC["tls"],
    "cert-name": _SEC["tls"], "cert-weak-key": _SEC["tls"], "cert-weak-signature": _SEC["tls"],
    "hsts-missing": _SEC["hsts"], "hsts-short": _SEC["hsts"], "hsts-invalid": _SEC["hsts"],
    "no-https-redirect": _SEC["https-redirect"],
    "no-compression": ("compression", "Turn on compression for web pages",
                       "Compressed pages download several times faster, especially on phones.",
                       HOST),
    "no-tls13": ("tls-modern", "Update the encryption the server supports",
                 "Modern encryption (TLS 1.3) is faster and safer for visitors.", HOST),
    "tls-modern-missing": ("tls-modern", "Update the encryption the server supports",
                           "Current browsers may refuse to connect.", HOST),
    "ipv6-unreachable": ("ipv6", "Fix the site's IPv6 address",
                         "Visitors on newer networks may not be able to reach the site.", HOST),
}


def http(data) -> Area:
    if not isinstance(data, dict) or not data.get("hosts"):
        raise NotChecked("no host in the tool output")
    h = data["hosts"][0]
    if h.get("error"):
        raise NotChecked(f"could not connect: {h['error']}")
    findings = h.get("findings") or []
    errors = [f for f in findings if f.get("level") == "error"]
    warns = [f for f in findings if f.get("level") == "warning"]
    area = Area("http", "http-protocol-check", checked=True,
                score=_clamp(100 - 30 * len(errors) - 10 * len(warns)))
    ch = h.get("checks") or {}
    alpn = ch.get("alpn") or {}
    h3 = (ch.get("http3") or {}).get("advertised")
    accepted = [row.get("version") for row in ch.get("tls_versions") or []
                if isinstance(row, dict) and row.get("status") == "accepted"]
    facts = []
    if alpn:
        facts.append("HTTP/2" if alpn.get("h2") else "no HTTP/2")
    if h3 is not None:
        facts.append("HTTP/3 advertised" if h3 else "no HTTP/3")
    if errors:
        area.verdict = f"Serious hosting problem: {errors[0].get('message')}."
    elif warns:
        area.verdict = ((f"{', '.join(facts)}; " if facts else "Hosting works; ")
                        + f"{len(warns)} outdated or missing setting(s) to update.")
    else:
        area.verdict = "Modern, well-configured hosting" + (f" ({', '.join(facts)})." if facts else ".")
    area.details.append(f"Host: {h.get('host')}:{h.get('port')}; " + (", ".join(facts) or "protocol facts not available"))
    if accepted:
        area.details.append("TLS versions accepted: " + ", ".join(accepted))
    cert = ch.get("certificate") or {}
    if cert.get("days_left") is not None:
        area.details.append(f"Certificate: {cert.get('days_left')} day(s) left"
                            + (f", issuer {cert['issuer']}" if cert.get("issuer") else ""))
    for f in findings:
        area.details.append(f"{f.get('level', '').upper()}: {f.get('code')}: {f.get('message')}")
    for f in errors + warns:
        concern, title, why, who = _HTTP.get(f.get("code"), (
            f.get("code", "http"), "Fix a hosting setting", f.get("message", ""), HOST))
        area.issues.append(Issue("http", concern, _sev(f.get("level", "")), title, why, who,
                                 f.get("message", "")))
    return area


NORMALIZERS = {
    "security-headers-audit": security,
    "web-vitals-lite": speed,
    "a11y-audit": accessibility,
    "consent-tracker-scan": privacy,
    "site-seo-crawler": seo,
    "og-card-check": social,
    "email-dns-check": email,
    "http-protocol-check": http,
}
