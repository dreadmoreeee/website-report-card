"""Command line interface."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .htmlreport import logo_src, render_html, valid_color
from .report import GRADES, build_report, render_json, render_markdown, render_text
from .tools import TOOLS, load_raw, make_target, run_all, save_raw

FORMATS = ("html", "md", "json")


def _formats(value: str) -> list[str]:
    items = [x.strip().lower() for x in value.split(",") if x.strip()]
    bad = [x for x in items if x not in FORMATS]
    if bad or not items:
        raise argparse.ArgumentTypeError(f"formats are a comma list of {', '.join(FORMATS)}")
    return items


def _tool(value: str) -> str:
    if value not in TOOLS:
        raise argparse.ArgumentTypeError(f"unknown tool {value!r}; one of: {', '.join(TOOLS)}")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="website-report-card",
        description="Run eight website checks and turn them into one client-friendly report card "
                    "(HTML, Markdown, JSON, optional PDF).")
    p.add_argument("url", nargs="?", help="site to check, e.g. https://example.com")
    p.add_argument("-o", "--out-dir", default="report-card", help="output folder (default: report-card)")
    p.add_argument("--name", default="report", help="base file name (default: report)")
    p.add_argument("--format", type=_formats, default=list(FORMATS),
                   help="comma list of html, md, json (default: all)")
    p.add_argument("--pdf", action="store_true", help="also write a PDF (needs Playwright and Chromium)")
    p.add_argument("--from-dir", metavar="DIR",
                   help="build the report from saved tool JSON files instead of running the tools")
    p.add_argument("--raw-dir", metavar="DIR",
                   help="where to keep each tool's raw JSON (default: OUT_DIR/raw)")
    p.add_argument("--local-src", metavar="DIR",
                   help="folder that holds the tool source folders (default: next to this "
                        "checkout, then the folder above it, then installed commands)")
    p.add_argument("--skip", type=_tool, action="append", default=[], metavar="TOOL",
                   help="do not run this tool (repeatable)")
    p.add_argument("--timeout", type=float, metavar="S",
                   help="timeout per tool in seconds (default: per tool, 90 to 300)")
    p.add_argument("--brand-name", default="", help="agency name shown in the header")
    p.add_argument("--brand-logo", metavar="FILE_OR_URL",
                   help="logo file (inlined) or https URL (loaded when the report is opened)")
    p.add_argument("--brand-color", metavar="HEX", help="header and accent colour, e.g. #1f4e79")
    p.add_argument("--prepared-for", default="", help="client name")
    p.add_argument("--date", default="", help="report date as shown (default: today, YYYY-MM-DD)")
    p.add_argument("--fail-under", choices=[g for _, g in GRADES], metavar="GRADE",
                   help="exit 1 if the overall grade is below this (A, B, C, D, F)")
    p.add_argument("-q", "--quiet", action="store_true", help="no progress messages on stderr")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def main(argv: list[str] | None = None, run=None, locator=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log = None if args.quiet else (lambda m: print(m, file=sys.stderr, flush=True))

    brand = {"name": args.brand_name}
    logo = None
    try:
        if args.brand_color:
            brand["color"] = valid_color(args.brand_color)
        if args.brand_logo:
            logo = logo_src(args.brand_logo)
            brand["logo"] = args.brand_logo
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    if args.from_dir:
        try:
            saved_url, runs = load_raw(args.from_dir)
        except (OSError, ValueError) as exc:
            parser.error(f"--from-dir: {exc}")
        url = args.url or saved_url
        if not url:
            parser.error("give the URL (run.json in --from-dir has none)")
    else:
        if not args.url:
            parser.error("the URL is required unless --from-dir is used")
        url = args.url
    try:
        target = make_target(url)
    except ValueError as exc:
        parser.error(str(exc))

    os.makedirs(args.out_dir, exist_ok=True)
    if not args.from_dir:
        keys = [k for k in TOOLS if k not in args.skip]
        kwargs = {"run": run} if run else {}
        if locator:
            kwargs["locator"] = locator
        runs = run_all(target, keys, local_src=args.local_src, timeout=args.timeout, log=log, **kwargs)
        save_raw(args.raw_dir or os.path.join(args.out_dir, "raw"), target, runs)

    report = build_report(target, runs, prepared_for=args.prepared_for, date=args.date, brand=brand)
    base = os.path.join(args.out_dir, args.name)
    written = []
    html_text = render_html(report, logo)
    if "html" in args.format:
        _write(base + ".html", html_text)
        written.append(base + ".html")
    if "md" in args.format:
        _write(base + ".md", render_markdown(report))
        written.append(base + ".md")
    if "json" in args.format:
        _write(base + ".json", render_json(report))
        written.append(base + ".json")
    code = 0
    if args.pdf:
        try:
            from .pdf import write_pdf
            write_pdf(html_text, base + ".pdf")
            written.append(base + ".pdf")
        except Exception as exc:  # Playwright missing, Chromium missing, crash
            print(f"PDF not written: {exc}".splitlines()[0], file=sys.stderr)
            code = 3

    sys.stdout.write(render_text(report))
    for path in written:
        sys.stdout.write(f"Wrote {path}\n")
    if args.fail_under:
        order = [g for _, g in GRADES]
        grade = report["grade"]
        if grade is None or order.index(grade) > order.index(args.fail_under):
            code = code or 1
    return code
