import pytest

from website_report_card import areas
from website_report_card.areas import NotChecked, metric_score


def test_scores_and_lights_from_canned_output(canned):
    expected = {
        "security-headers-audit": (72, "amber"),
        "web-vitals-lite": (79, "amber"),       # LCP needs improvement: capped at 79
        "a11y-audit": (78, "amber"),            # 100 - serious 15 - moderate 7
        "consent-tracker-scan": (68, "amber"),  # 100 - high 30 - low 2
        "site-seo-crawler": (92, "green"),
        "og-card-check": (59, "amber"),         # 100 - error 25 - 2 warnings x 8
        "email-dns-check": (90, "green"),
        "http-protocol-check": (80, "green"),
    }
    for key, (score, light) in expected.items():
        area = areas.NORMALIZERS[key](canned[key])
        assert area.checked
        assert (area.score, area.light) == (score, light), key
        assert area.verdict
        assert area.details


def test_speed_details_and_issue(canned):
    a = areas.speed(canned["web-vitals-lite"])
    assert "3.20 s" in a.verdict
    assert any("LCP" in d and "needs improvement" in d for d in a.details)
    (issue,) = a.issues
    assert issue.concern == "lcp" and issue.severity == "medium"
    assert "large image" in issue.why


def test_speed_poor_metric_caps_red(canned):
    data = canned["web-vitals-lite"]
    data["results"][0]["median"]["tbt_ms"] = 900.0
    a = areas.speed(data)
    assert a.score <= 49 and a.light == "red"
    assert {i.concern: i.severity for i in a.issues}["tbt"] == "high"


def test_speed_all_good_is_green(canned):
    data = canned["web-vitals-lite"]
    data["results"][0]["median"].update(lcp_ms=1200.0, tbt_ms=50.0, cls=0.0)
    a = areas.speed(data)
    assert a.score == 100 and a.light == "green" and not a.issues
    assert a.verdict.startswith("Loads quickly")


@pytest.mark.parametrize("value,expected", [(1000, 100), (2500, 100), (3250, 75), (4000, 50),
                                            (6000, 25), (8000, 0), (20000, 0)])
def test_metric_score(value, expected):
    assert metric_score(value, 2500, 4000) == pytest.approx(expected)


def test_plain_language_issues(canned):
    a11y = areas.accessibility(canned["a11y-audit"])
    assert a11y.issues[0].title == "Make pale or low-contrast text easier to read"
    assert a11y.issues[0].severity == "high"
    privacy = areas.privacy(canned["consent-tracker-scan"])
    assert privacy.issues[0].severity == "high"
    assert "Google Analytics" in privacy.issues[0].why and "not legal advice" in privacy.issues[0].why
    seo = areas.seo(canned["site-seo-crawler"])
    assert {i.title for i in seo.issues} == {"Fix broken links",
                                             "Keep page titles between 30 and 60 characters"}
    assert any("page limit" in d for d in seo.details)
    email = areas.email(canned["email-dns-check"])
    assert email.issues[0].title.startswith("Stop others from sending email")
    assert "DNS" in email.issues[0].who
    http = areas.http(canned["http-protocol-check"])
    assert {i.concern for i in http.issues} == {"tls-legacy", "hsts"}
    assert any("TLSv1.0, TLSv1.2, TLSv1.3" in d for d in http.details)
    social = areas.social(canned["og-card-check"])
    assert {i.concern for i in social.issues} == {"og-image", "og-length"}


def test_no_problems_verdicts(canned):
    data = canned["a11y-audit"]
    data["pages"][0]["violations"] = []
    a = areas.accessibility(data)
    assert a.score == 100 and "only part" in a.verdict
    data = canned["consent-tracker-scan"]
    data["summary"].update(high=0, low=0, trackers=[])
    data["findings"] = []
    p = areas.privacy(data)
    assert p.score == 100 and "Cookiebot" in p.verdict


@pytest.mark.parametrize("key,mutate,reason", [
    ("security-headers-audit", lambda d: d[0].update(error="connection refused"), "connection refused"),
    ("web-vitals-lite", lambda d: d["results"][0].update(runs_ok=0, errors=["net::ERR_NAME_NOT_RESOLVED"]),
     "ERR_NAME_NOT_RESOLVED"),
    ("a11y-audit", lambda d: d["pages"][0].update(error="Timeout 30000ms exceeded"), "Timeout"),
    ("consent-tracker-scan", lambda d: (d["summary"].update(pages_scanned=0),
                                        d["pages"][0].update(error="HTTP 503")), "HTTP 503"),
    ("site-seo-crawler", lambda d: d["summary"].update(pages_scored=0, notes=["robots.txt disallows /"]),
     "robots.txt"),
    ("og-card-check", lambda d: d[0].update(status=0, findings=[
        {"level": "error", "code": "fetch-failed", "message": "could not fetch page: timed out"}]), "timed out"),
    ("email-dns-check", lambda d: d["domains"][0].update(checks=[]), "no checks"),
    ("http-protocol-check", lambda d: d["hosts"][0].update(error="could not complete a TLS handshake"),
     "TLS handshake"),
])
def test_not_checked_when_the_site_could_not_be_read(canned, key, mutate, reason):
    data = canned[key]
    mutate(data)
    with pytest.raises(NotChecked, match=reason):
        areas.NORMALIZERS[key](data)


def test_empty_list_is_not_checked():
    with pytest.raises(NotChecked):
        areas.security([])
    with pytest.raises(NotChecked):
        areas.speed({"results": []})
