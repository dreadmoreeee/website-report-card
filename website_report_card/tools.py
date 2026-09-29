"""The eight source tools: how to find them, how to run them, how to keep their output."""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable
from urllib.parse import urlsplit

USER_AGENT = "website-report-card/1.0 (+https://github.com/dreadmoreeee/website-report-card)"

OK, FAILED, MISSING, SKIPPED = "ok", "failed", "missing", "skipped"


@dataclasses.dataclass(frozen=True)
class Target:
    url: str        # https://example.com/ (scheme and host, path kept)
    host: str       # example.com or example.com:8443
    domain: str     # example.com (no port, no leading www.)

    @property
    def origin(self) -> str:
        parts = urlsplit(self.url)
        return f"{parts.scheme}://{parts.netloc}"


def make_target(url: str) -> Target:
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"not an http(s) URL: {url}")
    host = parts.netloc.rsplit("@", 1)[-1].lower()
    domain = parts.hostname.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    path = parts.path or "/"
    query = f"?{parts.query}" if parts.query else ""
    return Target(url=f"{parts.scheme}://{host}{path}{query}", host=host, domain=domain)


@dataclasses.dataclass(frozen=True)
class Tool:
    key: str            # folder name and console script name, e.g. security-headers-audit
    module: str         # python -m <module>
    area: str           # area key it feeds
    build: Callable[[Target, str], list[str]]   # (target, work dir) -> arguments
    output: str = "-"   # "-" = JSON on stdout, else a path relative to the work dir
    timeout: float = 120.0


def _security(t: Target, work: str) -> list[str]:
    return [t.url, "--format", "json", "--delay", "1", "--user-agent", USER_AGENT]


def _vitals(t: Target, work: str) -> list[str]:
    # The default mobile User-Agent already carries the tool's product token; replacing it
    # would change what a phone sees, so it is kept.
    return [t.url, "--profile", "mobile", "--runs", "1", "--format", "json"]


def _a11y(t: Target, work: str) -> list[str]:
    return [t.url, "--format", "json", "--quiet", "--user-agent", USER_AGENT]


def _consent(t: Target, work: str) -> list[str]:
    return [t.url, "--pages", "1", "--quiet", "--json", os.path.join(work, "consent.json")]


def _seo(t: Target, work: str) -> list[str]:
    return [t.url, "--max-pages", "10", "--format", "json", "--delay", "1",
            "--out-dir", os.path.join(work, "seo"), "--user-agent", USER_AGENT]


def _og(t: Target, work: str) -> list[str]:
    return [t.url, "--no-preview", "--json", "-", "--delay", "1"]


def _email(t: Target, work: str) -> list[str]:
    return [t.domain, "--format", "json"]


def _http(t: Target, work: str) -> list[str]:
    return [t.origin, "--format", "json", "--fail-on", "never"]


TOOLS: dict[str, Tool] = {tool.key: tool for tool in (
    Tool("security-headers-audit", "security_headers_audit", "security", _security, timeout=90),
    Tool("web-vitals-lite", "web_vitals_lite", "speed", _vitals, timeout=180),
    Tool("a11y-audit", "a11y_audit", "accessibility", _a11y, timeout=180),
    Tool("consent-tracker-scan", "consent_tracker_scan", "privacy", _consent,
         output="consent.json", timeout=150),
    Tool("site-seo-crawler", "site_seo_crawler", "seo", _seo,
         output=os.path.join("seo", "report.json"), timeout=300),
    Tool("og-card-check", "og_card_check", "social", _og, timeout=90),
    Tool("email-dns-check", "email_dns_check", "email", _email, timeout=90),
    Tool("http-protocol-check", "http_protocol_check", "http", _http, timeout=150),
)}


@dataclasses.dataclass
class Run:
    """What happened when one tool ran (or why it did not)."""
    key: str
    status: str                 # ok, failed, missing, skipped
    reason: str = ""            # short, for the "Not checked" line
    exit_code: int | None = None
    seconds: float = 0.0
    command: list[str] = dataclasses.field(default_factory=list)
    stderr_tail: str = ""
    data: object = None         # parsed JSON when status is ok

    def meta(self) -> dict:
        d = dataclasses.asdict(self)
        d.pop("data")
        return d


def default_search_dirs() -> list[str]:
    """Folders next to this checkout, then one level up."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parent = os.path.dirname(here)
    return [parent, os.path.dirname(parent)]


def locate(tool: Tool, local_src: str | None = None) -> tuple[list[str], str | None, str | None]:
    """Return (command prefix, cwd, PYTHONPATH entry) or ([], None, None) when not found."""
    dirs = [local_src] if local_src else default_search_dirs()
    for base in dirs:
        src = os.path.join(base, tool.key)
        if os.path.isfile(os.path.join(src, tool.module, "__main__.py")):
            return [sys.executable, "-m", tool.module], src, src
    if not local_src:
        script = shutil.which(tool.key)
        if script:
            return [script], None, None
    return [], None, None


def _tail(text: str, lines: int = 8) -> str:
    rows = [r for r in (text or "").strip().splitlines() if r.strip()]
    return "\n".join(rows[-lines:])


def _last_line(text: str) -> str:
    rows = _tail(text, 1)
    return rows[:200]


def display_command(cmd: list[str], work: str) -> list[str]:
    """The command as recorded in reports: no local interpreter or temporary paths."""
    shown = ["python" if cmd and cmd[0] == sys.executable else os.path.basename(cmd[0])]
    return shown + [a.replace(work, "<tmp>").replace(os.sep, "/") if work in a else a
                    for a in cmd[1:]]


def run_tool(tool: Tool, target: Target, *, local_src: str | None = None,
             timeout: float | None = None, run=None, locator=locate) -> Run:
    """Run one tool and parse its JSON. Never raises for tool problems."""
    run = run or subprocess.run
    prefix, cwd, pythonpath = locator(tool, local_src)
    if not prefix:
        where = local_src or " or ".join(default_search_dirs())
        return Run(tool.key, MISSING, f"tool not installed (not found in {where} or on PATH)")
    limit = timeout if timeout else tool.timeout
    with tempfile.TemporaryDirectory(prefix="wrc-") as work:
        cmd = prefix + tool.build(target, work)
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        if pythonpath:
            old = env.get("PYTHONPATH")
            env["PYTHONPATH"] = pythonpath + os.pathsep + old if old else pythonpath
        start = time.monotonic()
        try:
            proc = run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=limit, env=env, cwd=cwd)
        except subprocess.TimeoutExpired:
            return Run(tool.key, FAILED, f"timed out after {limit:g} s", None,
                       time.monotonic() - start, display_command(cmd, work))
        except OSError as exc:
            return Run(tool.key, FAILED, f"could not start: {exc}", None,
                       time.monotonic() - start, display_command(cmd, work))
        secs = time.monotonic() - start
        stderr = _tail(proc.stderr)
        shown = display_command(cmd, work)
        if tool.output == "-":
            text = proc.stdout or ""
        else:
            path = os.path.join(work, tool.output)
            text = ""
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
    result = Run(tool.key, OK, "", proc.returncode, secs, shown, stderr)
    if not text.strip():
        result.status = FAILED
        why = _last_line(proc.stderr) or "no output"
        result.reason = f"no JSON output (exit {proc.returncode}): {why}"
        return result
    try:
        result.data = json.loads(text)
    except ValueError as exc:
        result.status = FAILED
        result.reason = f"output was not valid JSON (exit {proc.returncode}): {exc}"
    return result


def run_all(target: Target, keys: list[str] | None = None, *, local_src: str | None = None,
            timeout: float | None = None, run=None, locator=locate, log=None) -> dict[str, Run]:
    """Run the selected tools one after another (never in parallel, to stay polite)."""
    results: dict[str, Run] = {}
    for key, tool in TOOLS.items():
        if keys is not None and key not in keys:
            results[key] = Run(key, SKIPPED, "skipped with --skip")
            continue
        if log:
            log(f"running {key} ...")
        r = run_tool(tool, target, local_src=local_src, timeout=timeout, run=run, locator=locator)
        if log:
            state = r.status if r.status == OK else f"{r.status}: {r.reason}"
            log(f"  {key}: {state} ({r.seconds:.1f} s)")
        results[key] = r
    return results


# ---------------------------------------------------------------- raw files

RUN_FILE = "run.json"


def save_raw(raw_dir: str, target: Target, runs: dict[str, Run]) -> None:
    """Keep each tool's JSON as <tool>.json plus run.json with exit codes and reasons."""
    os.makedirs(raw_dir, exist_ok=True)
    for key, r in runs.items():
        if r.status == OK:
            with open(os.path.join(raw_dir, f"{key}.json"), "w", encoding="utf-8",
                      newline="\n") as fh:
                json.dump(r.data, fh, indent=2, ensure_ascii=True)
                fh.write("\n")
    meta = {"url": target.url, "tools": {k: r.meta() for k, r in runs.items()}}
    with open(os.path.join(raw_dir, RUN_FILE), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=True)
        fh.write("\n")


def load_raw(raw_dir: str) -> tuple[str | None, dict[str, Run]]:
    """Read saved tool JSON files. Returns (url from run.json or None, runs)."""
    if not os.path.isdir(raw_dir):
        raise FileNotFoundError(f"not a directory: {raw_dir}")
    meta: dict = {}
    path = os.path.join(raw_dir, RUN_FILE)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            meta = json.load(fh)
    saved = meta.get("tools") or {}
    runs: dict[str, Run] = {}
    for key in TOOLS:
        info = saved.get(key) or {}
        fields = {k: info[k] for k in ("exit_code", "seconds", "command", "stderr_tail")
                  if k in info}
        file = os.path.join(raw_dir, f"{key}.json")
        if os.path.isfile(file):
            try:
                with open(file, encoding="utf-8") as fh:
                    data = json.load(fh)
            except ValueError as exc:
                runs[key] = Run(key, FAILED, f"saved file {key}.json is not valid JSON: {exc}",
                                **fields)
                continue
            runs[key] = Run(key, OK, "", data=data, **fields)
        elif info.get("status") in (FAILED, MISSING, SKIPPED):
            runs[key] = Run(key, info["status"], info.get("reason") or "", **fields)
        else:
            runs[key] = Run(key, MISSING, f"no saved output ({key}.json)")
    return meta.get("url"), runs
