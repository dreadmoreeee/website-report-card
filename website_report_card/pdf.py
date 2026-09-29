"""Optional PDF output through headless Chromium (Playwright)."""

from __future__ import annotations


def write_pdf(html_text: str, path: str, timeout_ms: float = 30000) -> None:
    """Render the HTML report to a Letter-size PDF with backgrounds and all details open."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html_text, wait_until="load", timeout=timeout_ms)
            page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            page.emulate_media(media="print")
            page.pdf(path=path, format="Letter", print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()
