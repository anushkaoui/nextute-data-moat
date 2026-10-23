import pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "03_pitch_deck.html"
PDF = ROOT / "docs" / "03_pitch_deck.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
    page.goto(HTML.as_uri())
    page.wait_for_timeout(800)
    page.pdf(path=str(PDF), width="13.333in", height="7.5in", print_background=True, margin={"top":"0","bottom":"0","left":"0","right":"0"})
    browser.close()
print(f"wrote {PDF.name}")
