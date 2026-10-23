import pathlib
import markdown
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "02_validation_report.md"
HTML = ROOT / "docs" / "02_validation_report.html"
PDF = ROOT / "docs" / "02_validation_report.pdf"

body = markdown.Markdown(extensions=["tables", "toc", "sane_lists", "fenced_code"]).convert(SRC.read_text())
html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Validation report — Institute Intelligence</title>
<style>
@page {{ size: A4; margin: 18mm 16mm 18mm 16mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Arial, Helvetica, sans-serif; color: #172033; font-size: 10.2pt; line-height: 1.5; margin: 0; }}
h1 {{ font-size: 25pt; line-height: 1.12; color: #0f172a; margin: 0 0 10px; letter-spacing: -0.03em; }}
h1 + p strong {{ color: #1d4ed8; }}
h2 {{ font-size: 15pt; color: #0f172a; margin: 22px 0 8px; border-bottom: 1.5px solid #dbeafe; padding-bottom: 5px; page-break-after: avoid; }}
h3 {{ font-size: 11.4pt; color: #1e3a8a; margin: 15px 0 5px; page-break-after: avoid; }}
p {{ margin: 0 0 8px; }}
ul, ol {{ margin: 0 0 9px 18px; padding: 0; }}
li {{ margin: 0 0 3px; }}
table {{ width: 100%; border-collapse: collapse; margin: 8px 0 13px; font-size: 8.9pt; page-break-inside: avoid; }}
th {{ background: #0f172a; color: white; text-align: left; padding: 6px 7px; font-weight: 650; }}
td {{ border-bottom: 1px solid #e2e8f0; padding: 5px 7px; vertical-align: top; }}
tr:nth-child(even) td {{ background: #f8fafc; }}
code, pre {{ font-family: "Courier New", Courier, monospace; font-size: 8.6pt; }}
pre {{ background: #0f172a; color: #e2e8f0; padding: 10px 12px; border-radius: 6px; white-space: pre-wrap; }}
blockquote {{ margin: 10px 0; padding: 8px 12px; border-left: 3px solid #1d4ed8; background: #eff6ff; }}
hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 16px 0; }}
a {{ color: #1d4ed8; text-decoration: none; }}
strong {{ color: #0f172a; }}
</style></head><body>{body}</body></html>"""
HTML.write_text(html)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    page = browser.new_page()
    page.goto(HTML.as_uri())
    page.pdf(path=str(PDF), format="A4", print_background=True,
             margin={"top": "16mm", "bottom": "16mm", "left": "15mm", "right": "15mm"},
             display_header_footer=True,
             header_template="<div></div>",
             footer_template="<div style='font-size:8px;color:#64748b;width:100%;text-align:center;padding:0 15mm'>Institute Intelligence · Validation report · page <span class='pageNumber'></span> / <span class='totalPages'></span></div>")
    browser.close()
print(f"wrote {HTML.name} and {PDF.name}")
