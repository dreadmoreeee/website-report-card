import json
import os
import subprocess
import sys
import types

import pytest

from website_report_card import cli
from website_report_card.tools import (FAILED, MISSING, OK, SKIPPED, TOOLS, load_raw, locate,
                                       make_target, run_all, run_tool, save_raw)

TARGET = make_target("https://www.example.com")
BY_MODULE = {t.module: k for k, t in TOOLS.items()}


def fake_locator(tool, local_src=None):
    return [sys.executable, "-m", tool.module], None, None


def _arg(cmd, flag):
    return cmd[cmd.index(flag) + 1]


def make_fake_run(canned, overrides=None, calls=None):
    """A stand-in for subprocess.run that answers like each tool would."""
    overrides = overrides or {}

    def run(cmd, **kw):
        key = BY_MODULE[cmd[2]]
        if calls is not None:
            calls.append((key, cmd, kw))
        action = overrides.get(key)
        if isinstance(action, BaseException):
            raise action
        if callable(action):
            return action(cmd)
        text = json.dumps(canned[key])
        stdout = text
        if key == "consent-tracker-scan":
            with open(_arg(cmd, "--json"), "w", encoding="utf-8") as fh:
                fh.write(text)
            stdout = ""
        elif key == "site-seo-crawler":
            out = _arg(cmd, "--out-dir")
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as fh:
                fh.write(text)
            stdout = "Wrote report.json\n"
        return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="progress\n")
    return run


def done(code, stdout="", stderr=""):
    return lambda cmd: types.SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def test_commands_are_polite_and_parsed(canned):
    calls = []
    runs = run_all(TARGET, run=make_fake_run(canned, calls=calls), locator=fake_locator)
    assert all(r.status == OK for r in runs.values())
    assert runs["site-seo-crawler"].data["summary"]["pages_scored"] == 8
    assert runs["consent-tracker-scan"].data["summary"]["high"] == 1
    cmds = {k: c for k, c, _ in calls}
    assert [k for k, _, _ in calls] == list(TOOLS)            # one after another, in order
    assert _arg(cmds["site-seo-crawler"], "--max-pages") == "10"
    assert _arg(cmds["web-vitals-lite"], "--runs") == "1"
    assert _arg(cmds["web-vitals-lite"], "--profile") == "mobile"
    assert _arg(cmds["consent-tracker-scan"], "--pages") == "1"
    assert cmds["email-dns-check"][3] == "example.com"
    assert cmds["http-protocol-check"][3] == "https://www.example.com"
    for key in ("security-headers-audit", "a11y-audit", "site-seo-crawler"):
        assert _arg(cmds[key], "--user-agent").startswith("website-report-card/1.0 (+https://")
    for _, _, kw in calls:
        assert kw["timeout"] > 0 and kw["env"]["PYTHONUTF8"] == "1"


def test_missing_tool():
    r = run_tool(TOOLS["a11y-audit"], TARGET, locator=lambda t, s=None: ([], None, None),
                 run=lambda *a, **k: pytest.fail("must not run"))
    assert r.status == MISSING and "not installed" in r.reason


@pytest.mark.parametrize("override,status,reason", [
    (done(2, "", "Traceback ...\nplaywright._impl._errors.Error: Executable doesn't exist\n"),
     FAILED, "no JSON output (exit 2): playwright._impl._errors.Error: Executable doesn't exist"),
    (done(0, "this is { not json"), FAILED, "not valid JSON"),
    (subprocess.TimeoutExpired(["x"], 5), FAILED, "timed out after 5 s"),
    (OSError("permission denied"), FAILED, "could not start: permission denied"),
    (done(1, '[{"url": "https://www.example.com", "status": 200, "findings": []}]'), OK, ""),
])
def test_failing_tools(canned, override, status, reason):
    run = make_fake_run(canned, {"og-card-check": override})
    r = run_tool(TOOLS["og-card-check"], TARGET, run=run, locator=fake_locator, timeout=5)
    assert r.status == status
    assert reason in r.reason


def test_skip_and_file_output_missing(canned):
    runs = run_all(TARGET, ["email-dns-check", "consent-tracker-scan"], locator=fake_locator,
                   run=make_fake_run(canned, {"consent-tracker-scan": done(2, "", "browser missing")}))
    assert runs["security-headers-audit"].status == SKIPPED
    assert runs["email-dns-check"].status == OK
    assert runs["consent-tracker-scan"].status == FAILED
    assert "browser missing" in runs["consent-tracker-scan"].reason


def test_save_and_load_raw_round_trip(tmp_path, canned):
    runs = run_all(TARGET, locator=fake_locator,
                   run=make_fake_run(canned, {"a11y-audit": subprocess.TimeoutExpired(["x"], 180)}))
    save_raw(str(tmp_path), TARGET, runs)
    assert (tmp_path / "security-headers-audit.json").is_file()
    assert not (tmp_path / "a11y-audit.json").exists()
    url, loaded = load_raw(str(tmp_path))
    assert url == TARGET.url
    assert loaded["a11y-audit"].status == FAILED and "timed out" in loaded["a11y-audit"].reason
    assert loaded["email-dns-check"].data == canned["email-dns-check"]
    assert loaded["email-dns-check"].exit_code == 0


def test_load_raw_without_run_json(tmp_path, canned):
    (tmp_path / "email-dns-check.json").write_text(json.dumps(canned["email-dns-check"]))
    (tmp_path / "og-card-check.json").write_text("{broken")
    url, runs = load_raw(str(tmp_path))
    assert url is None
    assert runs["email-dns-check"].status == OK
    assert runs["og-card-check"].status == FAILED and "not valid JSON" in runs["og-card-check"].reason
    assert runs["a11y-audit"].status == MISSING and "no saved output" in runs["a11y-audit"].reason


def test_cli_runs_tools_and_writes_all_formats(tmp_path, canned, capsys):
    out = tmp_path / "out"
    code = cli.main(["https://www.example.com", "-o", str(out), "--quiet", "--brand-name", "Maple Web Co.",
                     "--brand-color", "#0a6640", "--prepared-for", "Riverbend Bakery", "--date", "2026-09-29"],
                    run=make_fake_run(canned, {"web-vitals-lite": done(2, "", "no browser")}),
                    locator=fake_locator)
    assert code == 0
    stdout = capsys.readouterr().out
    # (7790 - 79*15) / 85 = 77.7
    assert "Overall grade: C (78/100), 7 of 8 areas checked" in stdout
    assert "web-vitals-lite" in stdout and "failed: no JSON output (exit 2): no browser" in stdout
    for ext in ("html", "md", "json"):
        assert (out / f"report.{ext}").is_file()
    data = json.loads((out / "report.json").read_text())
    assert data["prepared_for"] == "Riverbend Bakery" and data["brand"]["color"] == "#0a6640"
    assert (out / "raw" / "run.json").is_file()

    # Re-render from the saved raw files without running anything.
    again = tmp_path / "again"
    code = cli.main(["--from-dir", str(out / "raw"), "-o", str(again), "--format", "json", "--quiet"],
                    run=lambda *a, **k: pytest.fail("must not run tools"))
    assert code == 0
    data2 = json.loads((again / "report.json").read_text())
    assert (data2["grade"], data2["score"], data2["url"]) == ("C", 78, "https://www.example.com/")
    assert data2["excluded"] == data["excluded"]
    assert not (again / "report.html").exists()


def test_cli_fail_under_and_usage_errors(tmp_path, canned, capsys):
    run = make_fake_run(canned)
    assert cli.main(["example.com", "-o", str(tmp_path), "-q", "--fail-under", "B"],
                    run=run, locator=fake_locator) == 1
    assert cli.main(["example.com", "-o", str(tmp_path), "-q", "--fail-under", "C"],
                    run=run, locator=fake_locator) == 0
    for argv in (["example.com", "--brand-color", "blue"], [], ["example.com", "--skip", "nope"],
                 ["example.com", "--format", "pdf"], ["--from-dir", str(tmp_path / "none")],
                 ["example.com", "--brand-logo", str(tmp_path / "missing.png")]):
        with pytest.raises(SystemExit) as exc:
            cli.main(argv + ["-o", str(tmp_path)], run=run, locator=fake_locator)
        assert exc.value.code == 2


FAKE_TOOL = """
import json, os, sys, time
args = sys.argv[1:]
mode = {mode!r}
data = {data!r}
if mode == "sleep":
    time.sleep(30)
if mode == "crash":
    sys.stderr.write("Traceback (most recent call last):\\nRuntimeError: boom\\n")
    sys.exit(2)
if "--json" in args and args[args.index("--json") + 1] != "-":
    open(args[args.index("--json") + 1], "w").write(data)
elif "--out-dir" in args:
    d = args[args.index("--out-dir") + 1]
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "report.json"), "w").write(data)
else:
    print(data)
"""


def test_real_subprocesses_with_fake_tool_folders(tmp_path, canned, capsys):
    src = tmp_path / "src"
    modes = {"a11y-audit": "sleep", "http-protocol-check": "crash", "og-card-check": None}
    for key, tool in TOOLS.items():
        if key in modes and modes[key] is None:
            continue                                 # og-card-check not installed at all
        pkg = src / key / tool.module
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "__main__.py").write_text(FAKE_TOOL.format(mode=modes.get(key, "ok"),
                                                          data=json.dumps(canned[key])))
    assert locate(TOOLS["email-dns-check"], str(src))[1] == str(src / "email-dns-check")
    assert locate(TOOLS["og-card-check"], str(src)) == ([], None, None)
    out = tmp_path / "out"
    code = cli.main(["https://www.example.com", "--local-src", str(src), "-o", str(out),
                     "--timeout", "3", "-q"])
    assert code == 0
    report = json.loads((out / "report.json").read_text())
    tools = {t["tool"]: t for t in report["tools"]}
    assert tools["a11y-audit"]["status"] == FAILED and "timed out after 3 s" in tools["a11y-audit"]["reason"]
    assert tools["http-protocol-check"]["reason"] == "no JSON output (exit 2): RuntimeError: boom"
    assert tools["og-card-check"]["status"] == MISSING
    assert tools["email-dns-check"]["status"] == OK and tools["email-dns-check"]["exit_code"] == 0
    # Recorded commands carry no local interpreter or temporary paths.
    assert tools["consent-tracker-scan"]["command"][:3] == ["python", "-m", "consent_tracker_scan"]
    assert "<tmp>/consent.json" in tools["consent-tracker-scan"]["command"]
    assert tools["a11y-audit"]["command"][0] == "python"
    assert report["areas_checked"] == 5
    assert {e["area"] for e in report["excluded"]} == {"accessibility", "http", "social"}
    assert "Not checked" in (out / "report.html").read_text(encoding="utf-8")


def test_pdf_output(tmp_path, canned):
    pytest.importorskip("playwright.sync_api")
    from website_report_card.htmlreport import render_html
    from website_report_card.pdf import write_pdf
    from website_report_card.report import build_report
    from website_report_card.tools import Run
    runs = {k: Run(k, OK, data=v) for k, v in canned.items()}
    html_text = render_html(build_report(TARGET, runs))
    path = tmp_path / "r.pdf"
    try:
        write_pdf(html_text, str(path))
    except Exception as exc:  # Chromium not installed on this machine
        pytest.skip(f"Chromium not available: {exc}")
    assert path.read_bytes()[:5] == b"%PDF-"
