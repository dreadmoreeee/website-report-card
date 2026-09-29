import datetime as dt
import json
import re

import pytest

from website_report_card.htmlreport import logo_src, render_html, valid_color
from website_report_card.report import (build_report, grade_for, render_json, render_markdown,
                                        render_text)
from website_report_card.tools import FAILED, MISSING, OK, Run, make_target

NOW = dt.datetime(2026, 9, 29, 12, 0, tzinfo=dt.timezone.utc)
TARGET = make_target("https://www.example.com")


def runs_from(canned, drop=(), fail=None):
    runs = {k: Run(k, OK, exit_code=0, seconds=1.0, data=v) for k, v in canned.items()}
    for k in drop:
        runs[k] = Run(k, MISSING, "tool not installed")
    for k, reason in (fail or {}).items():
        runs[k] = Run(k, FAILED, reason, exit_code=2)
    return runs


def test_grade_uses_documented_weights(canned):
    r = build_report(TARGET, runs_from(canned), now=NOW)
    # 72*20 + 79*15 + 78*15 + 68*15 + 92*15 + 90*10 + 59*5 + 80*5 = 7790 -> 78
    assert (r["score"], r["grade"]) == (78, "C")
    assert r["areas_checked"] == 8 and r["excluded"] == []
    assert sum(r["weights"].values()) == 100
    assert r["date"] == "2026-09-29"


def test_missing_areas_are_excluded_and_stated(canned):
    runs = runs_from(canned, drop=["web-vitals-lite"], fail={"email-dns-check": "timed out after 90 s"})
    r = build_report(TARGET, runs, now=NOW)
    # (7790 - 79*15 - 90*10) / 75 = 76.07 -> 76
    assert (r["score"], r["grade"]) == (76, "C")
    assert r["areas_checked"] == 6
    assert {e["area"]: e["reason"] for e in r["excluded"]} == {
        "speed": "tool not installed", "email": "timed out after 90 s"}
    speed = next(a for a in r["areas"] if a["key"] == "speed")
    assert speed["verdict"] == "Not checked: tool not installed" and speed["light"] is None


def test_unexpected_json_shape_is_not_checked(canned):
    canned["og-card-check"] = {"surprise": True}
    canned["a11y-audit"] = {"pages": [{"violations": "not a list of dicts"}]}
    r = build_report(TARGET, runs_from(canned), now=NOW)
    reasons = {e["area"]: e["reason"] for e in r["excluded"]}
    assert set(reasons) == {"social", "accessibility"}
    assert reasons["accessibility"].startswith("unexpected output format")


def test_nothing_checked_means_no_grade(canned):
    r = build_report(TARGET, runs_from(canned, drop=list(canned)), now=NOW)
    assert r["grade"] is None and r["score"] is None and r["top_fixes"] == []
    assert "not graded" in render_text(r)
    assert "Not graded" in render_html(r)


def test_top_fixes_most_severe_first_one_per_area_and_deduplicated(canned):
    r = build_report(TARGET, runs_from(canned), now=NOW)
    fixes = r["top_fixes"]
    assert [f["area"] for f in fixes] == ["security", "accessibility", "privacy"]
    assert fixes[0]["title"] == "Tell browsers to always use the secure connection"
    assert all(f["severity"] == "high" and f["why"] and f["who"] for f in fixes)
    # HSTS is reported by two tools; it must appear once (the higher severity).
    all_titles = [i["title"] for a in r["areas"] for i in a["issues"]]
    assert all_titles.count("Tell browsers to always use the secure connection") == 2
    assert [f["title"] for f in fixes].count("Tell browsers to always use the secure connection") == 1


def test_top_fixes_fill_from_same_area_when_few_areas(canned):
    only = {"a11y-audit": canned["a11y-audit"]}
    runs = runs_from(canned, drop=[k for k in canned if k not in only])
    fixes = build_report(TARGET, runs, now=NOW)["top_fixes"]
    assert [f["area"] for f in fixes] == ["accessibility", "accessibility"]


def test_text_and_markdown(canned):
    r = build_report(TARGET, runs_from(canned, fail={"http-protocol-check": "timed out after 150 s"}),
                     prepared_for="Riverbend Bakery", brand={"name": "Maple Web Co."}, now=NOW)
    text = render_text(r)
    assert "Overall grade: C" in text and "7 of 8 areas checked" in text
    assert "AMBER  Security" in text and "Top 3 fixes:" in text
    assert "http-protocol-check" in text and "failed: timed out after 150 s" in text
    md = render_markdown(r)
    assert md.startswith("# Website report card: https://www.example.com/")
    assert "Prepared for: Riverbend Bakery" in md and "Prepared by: Maple Web Co." in md
    assert md.count("<details>") == 8 and "| HTTP and hosting | not checked | - |" in md
    assert json.loads(render_json(r))["grade"] == r["grade"]


def test_html_is_self_contained_and_print_friendly(canned):
    r = build_report(TARGET, runs_from(canned), brand={"name": "Maple <Web> Co.", "color": "#0a6640"},
                     prepared_for="Riverbend Bakery", now=NOW)
    page = render_html(r, logo="data:image/png;base64,AAAA")
    assert page.startswith("<!DOCTYPE html>") and '<html lang="en">' in page
    assert not re.search(r'(?:src|href)\s*=\s*"(?:https?:)?//', page)
    assert "<link" not in page and "@import" not in page
    assert "@media print" in page and "break-inside:avoid" in page
    assert "details::details-content" in page and "beforeprint" in page
    assert page.count("<details>") == 8
    assert "Maple &lt;Web&gt; Co." in page and "--brand:#0a6640" in page
    assert 'src="data:image/png;base64,AAAA"' in page
    assert "Riverbend Bakery" in page
    assert "Tell browsers to always use the secure connection" in page


@pytest.mark.parametrize("value,expected", [("#1F4E79", "#1f4e79"), ("#0a6", "#00aa66"),
                                            (" #abcdef ", "#abcdef")])
def test_valid_color(value, expected):
    assert valid_color(value) == expected


@pytest.mark.parametrize("value", ["red", "#12345", "1f4e79", "#1f4e79;background:url(x)", "", "#ggg"])
def test_invalid_color(value):
    with pytest.raises(ValueError):
        valid_color(value)


def test_logo_inlined_as_data_uri(tmp_path):
    png = tmp_path / "logo.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    assert logo_src(str(png)) == "data:image/png;base64,iVBORw0KGgpmYWtl"
    assert logo_src("https://cdn.example.com/logo.svg") == "https://cdn.example.com/logo.svg"
    txt = tmp_path / "logo.txt"
    txt.write_text("x")
    with pytest.raises(ValueError):
        logo_src(str(txt))


@pytest.mark.parametrize("score,grade", [(100, "A"), (90, "A"), (89, "B"), (80, "B"), (70, "C"),
                                         (60, "D"), (59, "F"), (0, "F")])
def test_grade_bands(score, grade):
    assert grade_for(score) == grade


def test_make_target():
    t = make_target("www.Example.com")
    assert (t.url, t.host, t.domain, t.origin) == ("https://www.example.com/", "www.example.com",
                                                   "example.com", "https://www.example.com")
    t = make_target("http://example.ca:8080/en/?a=1")
    assert (t.url, t.domain, t.origin) == ("http://example.ca:8080/en/?a=1", "example.ca",
                                           "http://example.ca:8080")
    with pytest.raises(ValueError):
        make_target("ftp://example.com")
