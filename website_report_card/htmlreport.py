"""Self-contained HTML report: inline CSS, no external requests, print friendly."""

from __future__ import annotations

import base64
import html
import mimetypes
import os
import re

from .areas import TITLES
from .tools import OK

DEFAULT_COLOR = "#1f4e79"
LIGHT_COLOR = {"green": "#1a7f37", "amber": "#9a6700", "red": "#c62828", None: "#6b7280"}
LIGHT_TEXT = {"green": "Good", "amber": "Needs work", "red": "Poor", None: "Not checked"}
GRADE_COLOR = {"A": "#1a7f37", "B": "#2f7d32", "C": "#9a6700", "D": "#c2410c", "F": "#c62828",
               None: "#6b7280"}
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp"}
MAX_LOGO_BYTES = 1_000_000


def valid_color(value: str) -> str:
    """Return a normalised #rrggbb colour or raise ValueError."""
    value = (value or "").strip()
    if not _HEX.match(value):
        raise ValueError(f"not a hex colour like #1f4e79: {value!r}")
    if len(value) == 4:
        value = "#" + "".join(c * 2 for c in value[1:])
    return value.lower()


def logo_src(value: str) -> str:
    """A file becomes a data: URI; an http(s) URL is used as is (the report then loads it)."""
    if re.match(r"^https?://", value, re.I):
        return value
    ext = os.path.splitext(value)[1].lower()
    mime = _LOGO_TYPES.get(ext) or mimetypes.guess_type(value)[0]
    if not mime or not mime.startswith("image/"):
        raise ValueError(f"logo must be a PNG, JPEG, GIF, SVG or WebP file: {value}")
    size = os.path.getsize(value)
    if size > MAX_LOGO_BYTES:
        raise ValueError(f"logo is {size:,} bytes; keep it under {MAX_LOGO_BYTES:,}")
    with open(value, "rb") as fh:
        data = base64.b64encode(fh.read()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def _text_on(color: str) -> str:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1f2328;
background:#f4f5f7;line-height:1.45;font-size:15px}
.wrap{max-width:980px;margin:0 auto;padding:0 20px 40px}
header.top{background:var(--brand);color:var(--brand-text);padding:18px 0}
header.top .wrap{display:flex;align-items:center;gap:16px;padding-bottom:0}
header.top img{max-height:48px;max-width:180px;background:#fff;border-radius:6px;padding:4px}
header.top .agency{font-weight:600;font-size:17px}
header.top .meta{margin-left:auto;text-align:right;font-size:13px;opacity:.95}
h1{font-size:26px;margin:26px 0 4px}
h2{font-size:19px;margin:28px 0 12px}
.url{color:#57606a;word-break:break-all;margin:0 0 18px}
.summary{display:flex;gap:22px;align-items:center;background:#fff;border-radius:12px;padding:20px;
border:1px solid #d8dee4}
.grade{flex:0 0 auto;width:104px;height:104px;border-radius:50%;display:flex;flex-direction:column;
align-items:center;justify-content:center;color:#fff;font-weight:700}
.grade .letter{font-size:46px;line-height:1}
.grade .num{font-size:13px;font-weight:600}
.summary p{margin:4px 0}
.lights{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:8px;font-size:13px}
.dot{display:inline-block;width:12px;height:12px;border-radius:50%;vertical-align:-1px;margin-right:5px}
.fixes{list-style:none;padding:0;margin:0;counter-reset:fix}
.fixes li{background:#fff;border:1px solid #d8dee4;border-left:6px solid var(--brand);border-radius:10px;
padding:14px 16px 12px 52px;margin-bottom:10px;position:relative;break-inside:avoid}
.fixes li::before{counter-increment:fix;content:counter(fix);position:absolute;left:14px;top:13px;
width:26px;height:26px;border-radius:50%;background:var(--brand);color:var(--brand-text);
text-align:center;font-weight:700;line-height:26px}
.fixes .what{font-weight:600;font-size:16px}
.fixes .area{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#57606a}
.fixes p{margin:4px 0 0}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px}
.card{background:#fff;border:1px solid #d8dee4;border-top:6px solid var(--light);border-radius:10px;
padding:14px 16px;break-inside:avoid;page-break-inside:avoid}
.card h3{margin:0;font-size:16px;display:flex;align-items:center;gap:8px}
.card .score{margin-left:auto;font-size:15px;color:var(--light);white-space:nowrap}
.card .state{font-size:12px;font-weight:600;color:var(--light);text-transform:uppercase;letter-spacing:.04em}
.card .verdict{margin:8px 0}
.card.off{border-top-color:#9ca3af}
.card.off .verdict{color:#57606a}
details{margin-top:6px;font-size:13px}
summary{cursor:pointer;color:#0b5cad}
details ul{margin:8px 0 0;padding-left:18px;overflow-wrap:anywhere}
details li{margin:2px 0}
details li.sub{list-style:circle;margin-left:18px}
.tool{color:#57606a;font-size:12px;margin-top:6px}
table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}
th,td{border:1px solid #d8dee4;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f6f8fa}
.note{font-size:13px;color:#57606a}
footer{margin-top:28px;font-size:12px;color:#57606a}
@media print{
 @page{size:Letter;margin:14mm}
 body{background:#fff;font-size:12px}
 .wrap{max-width:none;padding:0}
 header.top{-webkit-print-color-adjust:exact;print-color-adjust:exact}
 header.top .wrap{padding:0 12px}
 .grade,.dot,.fixes li::before{-webkit-print-color-adjust:exact;print-color-adjust:exact}
 .card,.fixes li,.summary,table tr{break-inside:avoid;page-break-inside:avoid}
 .cards{display:block}
 .card{margin-bottom:10px}
 h2{break-after:avoid;page-break-after:avoid}
 summary{color:#1f2328;list-style:none}
 summary::-webkit-details-marker{display:none}
 details::details-content{content-visibility:visible;display:block}
}
"""

# Chromium hides the content of a closed <details> from print; open them all first.
PRINT_SCRIPT = ("<script>window.addEventListener('beforeprint',function(){"
                "document.querySelectorAll('details').forEach(function(d){d.open=true;});});</script>")


def render_html(report: dict, logo: str | None = None) -> str:
    brand = report.get("brand") or {}
    color = brand.get("color") or DEFAULT_COLOR
    agency = brand.get("name") or ""
    grade = report.get("grade")
    out = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f"<title>Website report card: {_e(report['domain'])}</title>",
           f"<style>:root{{--brand:{color};--brand-text:{_text_on(color)}}}{CSS}</style>",
           PRINT_SCRIPT, "</head>", "<body>"]
    out.append('<header class="top"><div class="wrap">')
    if logo:
        out.append(f'<img src="{_e(logo)}" alt="{_e(agency or "Logo")}">')
    out.append(f'<div class="agency">{_e(agency) if agency else "Website report card"}</div>')
    meta = []
    if report.get("prepared_for"):
        meta.append(f"Prepared for {_e(report['prepared_for'])}")
    meta.append(_e(report["date"]))
    out.append(f'<div class="meta">{"<br>".join(meta)}</div></div></header>')

    out.append('<main class="wrap">')
    out.append(f"<h1>Website report card</h1><p class=\"url\">{_e(report['url'])}</p>")
    out.append('<section class="summary" aria-label="Overall grade">')
    gcolor = GRADE_COLOR.get(grade, GRADE_COLOR[None])
    if grade:
        out.append(f'<div class="grade" style="background:{gcolor}"><span class="letter">{_e(grade)}</span>'
                   f'<span class="num">{report["score"]}/100</span></div>')
    else:
        out.append(f'<div class="grade" style="background:{gcolor}"><span class="num">Not graded</span></div>')
    out.append("<div>")
    out.append(f"<p><strong>Overall grade {_e(grade or '-')}</strong>, based on "
               f"{report['areas_checked']} of {report['areas_total']} areas.</p>")
    if report["excluded"]:
        out.append("<p class=\"note\">Not checked, so not in the grade: "
                   + "; ".join(f"{_e(x['title'])} ({_e(x['reason'])})" for x in report["excluded"])
                   + ".</p>")
    out.append('<div class="lights">')
    for a in report["areas"]:
        out.append(f'<span><span class="dot" style="background:{LIGHT_COLOR[a["light"]]}"></span>'
                   f'{_e(a["title"])}: {_e(LIGHT_TEXT[a["light"]])}</span>')
    out.append("</div></div></section>")

    out.append("<h2>The most important fixes</h2>")
    if report["top_fixes"]:
        out.append('<ol class="fixes">')
        for f in report["top_fixes"]:
            out.append(f'<li><div class="area">{_e(f["area_title"])} &middot; {_e(f["severity"])} priority</div>'
                       f'<div class="what">{_e(f["title"])}</div>'
                       f'<p><strong>Why it matters:</strong> {_e(f["why"])}</p>'
                       f'<p><strong>Who would fix it:</strong> {_e(f["who"])}</p></li>')
        out.append("</ol>")
    else:
        out.append('<p class="note">No fixes to suggest from the checks that ran.</p>')

    out.append('<h2>Report card</h2><div class="cards">')
    for a in report["areas"]:
        lc = LIGHT_COLOR[a["light"]]
        cls = "card" if a["checked"] else "card off"
        score = f'<span class="score">{a["score"]}/100</span>' if a["checked"] else ""
        out.append(f'<section class="{cls}" style="--light:{lc}">'
                   f'<h3><span class="dot" style="background:{lc}"></span>{_e(a["title"])}{score}</h3>'
                   f'<div class="state">{_e(LIGHT_TEXT[a["light"]])}</div>'
                   f'<p class="verdict">{_e(a["verdict"])}</p>')
        if a["details"]:
            out.append("<details><summary>Technical details</summary><ul>")
            for d in a["details"]:
                if d.startswith("  "):  # sub-line (selector, record to publish)
                    out.append(f'<li class="sub">{_e(d.strip().removeprefix("- "))}</li>')
                else:
                    out.append(f"<li>{_e(d)}</li>")
            out.append("</ul></details>")
        out.append(f'<div class="tool">Checked with {_e(a["tool"])}</div></section>')
    out.append("</div>")

    out.append("<h2>How this report was made</h2>")
    out.append("<table><thead><tr><th>Tool</th><th>Area</th><th>Status</th><th>Time</th></tr></thead><tbody>")
    for t in report["tools"]:
        state = "ran" if t["status"] == OK else f"{t['status']}: {t['reason']}"
        if t["status"] == OK and t["exit_code"] not in (None, 0):
            state += f" (exit {t['exit_code']}: problems found)"
        out.append(f"<tr><td>{_e(t['tool'])}</td><td>{_e(TITLES[t['area']])}</td>"
                   f"<td>{_e(state)}</td><td>{t['seconds']:.1f} s</td></tr>")
    out.append("</tbody></table>")
    weights = ", ".join(f"{_e(TITLES[k])} {w}%" for k, w in report["weights"].items())
    out.append(f'<p class="note">Overall grade: weighted average of the area scores ({weights}). '
               "Areas that were not checked are left out and the other weights are scaled up. "
               "A from 90, B from 80, C from 70, D from 60, F below. Lights: green from 80, "
               "amber from 50, red below 50. Speed is measured on a simulated mid-range phone "
               "with a slow connection, one page load.</p>")
    out.append('<p class="note">Automated checks catch many common problems, not all of them. '
               "Privacy notes are general information, not legal advice.</p>")
    out.append(f"<footer>Generated {_e(report['generated'])} by website-report-card "
               f"{_e(report['version'])}.</footer>")
    out.append("</main></body></html>")
    return "\n".join(out) + "\n"
