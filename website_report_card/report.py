"""Build the report (areas, grade, top fixes) and render it as text, Markdown or JSON."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json

from . import __version__
from .areas import AREAS, NORMALIZERS, TITLES, WEIGHTS, Area, Issue, NotChecked
from .tools import MISSING, OK, SKIPPED, TOOLS, Run, Target

GRADES = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]
LIGHT_LABEL = {"green": "GREEN", "amber": "AMBER", "red": "RED", None: "--"}


def grade_for(score: float) -> str:
    return next(g for bar, g in GRADES if score >= bar)


def build_area(key: str, run: Run) -> Area:
    tool = TOOLS[key]
    if run.status != OK:
        reason = run.reason or ("not run" if run.status == SKIPPED else "tool failed")
        return Area(tool.area, key, reason=reason)
    try:
        area = NORMALIZERS[key](run.data)
    except NotChecked as exc:
        return Area(tool.area, key, reason=str(exc))
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        return Area(tool.area, key, reason=f"unexpected output format ({type(exc).__name__}: {exc})")
    unique: dict[str, Issue] = {}
    for issue in area.issues:     # one entry per concern, the most severe
        if issue.concern not in unique or issue.rank() > unique[issue.concern].rank():
            unique[issue.concern] = issue
    area.issues = list(unique.values())
    return area


def top_fixes(areas: list[Area], limit: int = 3) -> list[Issue]:
    """Most severe first; one per area where possible, then fill; same concern only once."""
    best: dict[str, Issue] = {}
    for a in areas:
        for issue in a.issues:
            kept = best.get(issue.concern)
            if kept is None or issue.rank() > kept.rank():
                best[issue.concern] = issue
    ordered = sorted(best.values(), key=lambda i: i.rank(), reverse=True)
    picked: list[Issue] = []
    for issue in ordered:
        if len(picked) < limit and all(p.area != issue.area for p in picked):
            picked.append(issue)
    for issue in ordered:
        if len(picked) < limit and issue not in picked:
            picked.append(issue)
    return sorted(picked, key=lambda i: i.rank(), reverse=True)


def build_report(target: Target, runs: dict[str, Run], *, prepared_for: str = "",
                 date: str = "", brand: dict | None = None, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    by_area = {TOOLS[k].area: build_area(k, runs.get(k) or Run(k, MISSING, "not run"))
               for k in TOOLS}
    areas = [by_area[k] for k, _, _ in AREAS]
    checked = [a for a in areas if a.checked]
    score = grade = None
    if checked:
        total = sum(a.weight for a in checked)
        score = round(sum(a.score * a.weight for a in checked) / total)
        grade = grade_for(score)
    fixes = top_fixes(areas)
    return {
        "tool": "website-report-card",
        "version": __version__,
        "url": target.url,
        "domain": target.domain,
        "generated": now.replace(microsecond=0).isoformat(),
        "date": date or now.date().isoformat(),
        "prepared_for": prepared_for,
        "brand": dict(brand or {}),
        "grade": grade,
        "score": score,
        "weights": dict(WEIGHTS),
        "areas_checked": len(checked),
        "areas_total": len(areas),
        "excluded": [{"area": a.key, "title": a.title, "reason": a.reason}
                     for a in areas if not a.checked],
        "areas": [_area_dict(a) for a in areas],
        "top_fixes": [_issue_dict(i) for i in fixes],
        "tools": [{"tool": k, "area": TOOLS[k].area, **_run_dict(runs.get(k))} for k in TOOLS],
    }


def _issue_dict(i: Issue) -> dict:
    d = dataclasses.asdict(i)
    d["area_title"] = TITLES[i.area]
    return d


def _area_dict(a: Area) -> dict:
    return {"key": a.key, "title": a.title, "weight": a.weight, "tool": a.tool,
            "checked": a.checked, "score": a.score, "light": a.light,
            "verdict": a.verdict if a.checked else f"Not checked: {a.reason}",
            "reason": a.reason, "details": list(a.details),
            "issues": [_issue_dict(i) for i in a.issues]}


def _run_dict(r: Run | None) -> dict:
    if r is None:
        return {"status": MISSING, "reason": "not run", "exit_code": None, "seconds": 0.0,
                "command": []}
    return {"status": r.status, "reason": r.reason, "exit_code": r.exit_code,
            "seconds": round(r.seconds or 0.0, 1), "command": list(r.command or [])}


# ---------------------------------------------------------------- renderers

def overall_line(report: dict) -> str:
    n, total = report["areas_checked"], report["areas_total"]
    if report["grade"] is None:
        return f"Overall grade: not graded (0 of {total} areas checked)"
    return f"Overall grade: {report['grade']} ({report['score']}/100), {n} of {total} areas checked"


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=True) + "\n"


def render_text(report: dict) -> str:
    out = [f"Website report card: {report['url']}", overall_line(report), ""]
    width = max(len(a["title"]) for a in report["areas"])
    for a in report["areas"]:
        score = f"{a['score']:>3}" if a["checked"] else "  -"
        out.append(f"  {LIGHT_LABEL[a['light']]:<5}  {a['title']:<{width}}  {score}  {a['verdict']}")
    if report["excluded"]:
        out.append("")
        out.append("Not in the grade: " + ", ".join(e["title"] for e in report["excluded"]))
    out += ["", f"Top {len(report['top_fixes'])} fixes:" if report["top_fixes"] else "No fixes to suggest."]
    for n, f in enumerate(report["top_fixes"], 1):
        out.append(f" {n}. [{f['area_title']}] {f['title']} ({f['severity']})")
        out.append(f"    Why: {f['why']}")
        out.append(f"    Who: {f['who']}")
    out += ["", "Tools:"]
    kw = max(len(t["tool"]) for t in report["tools"])
    for t in report["tools"]:
        code = "-" if t["exit_code"] is None else str(t["exit_code"])
        state = t["status"] if t["status"] == OK else f"{t['status']}: {t['reason']}"
        out.append(f"  {t['tool']:<{kw}}  exit {code:<2} {t['seconds']:>6.1f} s  {state}")
    return "\n".join(out) + "\n"


def _md(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict) -> str:
    brand = report.get("brand") or {}
    lines = [f"# Website report card: {report['url']}", ""]
    meta = []
    if report.get("prepared_for"):
        meta.append(f"Prepared for: {report['prepared_for']}")
    if brand.get("name"):
        meta.append(f"Prepared by: {brand['name']}")
    meta.append(f"Date: {report['date']}")
    lines += ["  \n".join(meta), "", f"**{overall_line(report)}**", ""]
    if report["excluded"]:
        lines.append("Not in the grade (not checked): "
                     + "; ".join(f"{e['title']} ({e['reason']})" for e in report["excluded"]))
        lines.append("")
    lines += ["| Area | Light | Score | Verdict |", "|---|---|---:|---|"]
    for a in report["areas"]:
        score = str(a["score"]) if a["checked"] else "-"
        light = LIGHT_LABEL[a["light"]].lower() if a["checked"] else "not checked"
        lines.append(f"| {_md(a['title'])} | {light} | {score} | {_md(a['verdict'])} |")
    lines += ["", "## Top fixes", ""]
    if not report["top_fixes"]:
        lines += ["No fixes to suggest from the checks that ran.", ""]
    for n, f in enumerate(report["top_fixes"], 1):
        lines += [f"{n}. **{f['title']}** ({f['area_title']}, {f['severity']} priority)  ",
                  f"   Why it matters: {f['why']}  ",
                  f"   Who would fix it: {f['who']}", ""]
    lines += ["## Details", ""]
    for a in report["areas"]:
        head = f"{a['title']}: {a['score']}/100 ({a['light']})" if a["checked"] else f"{a['title']}: not checked"
        lines += [f"<details><summary>{head}</summary>", "", a["verdict"], "",
                  f"Tool: `{a['tool']}`", ""]
        if a["details"]:
            lines += ["```text", *a["details"], "```", ""]
        lines += ["</details>", ""]
    lines += ["## How this report was made", "",
              "| Tool | Status | Exit code | Time |", "|---|---|---|---:|"]
    for t in report["tools"]:
        code = "-" if t["exit_code"] is None else str(t["exit_code"])
        state = t["status"] if t["status"] == OK else f"{t['status']}: {t['reason']}"
        lines.append(f"| {t['tool']} | {_md(state)} | {code} | {t['seconds']:.1f} s |")
    lines += ["", "Grade weights: " + ", ".join(f"{TITLES[k]} {w}" for k, w in report["weights"].items())
              + ". Areas that were not checked are left out and the remaining weights are scaled up. "
              "A >= 90, B >= 80, C >= 70, D >= 60, F below. Lights: green >= 80, amber >= 50, red below.",
              "", "Automated checks catch many common problems, not all of them. The privacy notes "
              "are general information, not legal advice.", ""]
    return "\n".join(lines)
