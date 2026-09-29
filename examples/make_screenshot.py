"""Render the first screen of an HTML report to a small PNG (used for the README).

    python examples/make_screenshot.py examples/demarkstudio-report.html examples/screenshot.png
"""

import pathlib
import sys

from playwright.sync_api import sync_playwright


def main(src: str, dest: str, width: int = 900, height: int = 1150) -> None:
    html = pathlib.Path(src).read_text(encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(html, wait_until="load")
        page.screenshot(path=dest)
        browser.close()
    try:  # optional: fewer colours, much smaller file
        from PIL import Image
        img = Image.open(dest).convert("RGB")
        img.quantize(colors=128, method=Image.Quantize.MEDIANCUT).save(dest, optimize=True)
    except ImportError:
        pass
    print(f"{dest}: {pathlib.Path(dest).stat().st_size:,} bytes")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
