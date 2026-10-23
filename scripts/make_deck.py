from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"

NAVY = RGBColor(0x0F, 0x17, 0x2A)
NAVY2 = RGBColor(0x1E, 0x29, 0x3B)
BLUE = RGBColor(0x1D, 0x4E, 0xD8)
SKY = RGBColor(0xDB, 0xEA, 0xFE)
PALE = RGBColor(0xEF, 0xF6, 0xFF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x17, 0x20, 0x33)
SLATE = RGBColor(0x64, 0x74, 0x8B)
LINE = RGBColor(0xE2, 0xE8, 0xF0)
GREEN = RGBColor(0x16, 0xA3, 0x4A)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)
RED = RGBColor(0xDC, 0x26, 0x26)
MUTED = RGBColor(0x94, 0xA3, 0xB8)
FONT = "Arial"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def new_slide(bg=WHITE):
    s = prs.slides.add_slide(BLANK)
    fill = s.background.fill
    fill.solid()
    fill.fore_color.rgb = bg
    return s


def rect(s, x, y, w, h, fill=None, line=None, radius=True, line_w=1):
    shape = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                               Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        shape.adjustments[0] = 0.06
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid(); shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line; shape.line.width = Pt(line_w)
    shape.shadow.inherit = False
    return shape


def text(s, x, y, w, h, value, size=14, bold=False, color=INK, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, space=4, italic=False, font=FONT, line_spacing=1.0):
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = 0; tf.margin_right = 0
    tf.margin_top = 0; tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = str(value).split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.alignment = align
        p.space_after = Pt(space)
        p.line_spacing = line_spacing
        for run in p.runs:
            run.font.name = font
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.color.rgb = color
    return box


def kicker(s, text_value, color=BLUE, y=0.52):
    text(s, 0.72, y, 11.8, 0.3, text_value.upper(), 10.5, True, color, space=0)


def title(s, value, sub=None, size=30, y=0.88, color=INK):
    text(s, 0.72, y, 11.9, 0.9, value, size, True, color, space=2, line_spacing=1.0)
    if sub:
        text(s, 0.72, y + 0.92, 11.7, 0.55, sub, 13.5, False, SLATE, space=0)


def footer(s, n, source=None):
    line = s.shapes.add_connector(1, Inches(0.72), Inches(7.03), Inches(12.61), Inches(7.03))
    line.line.color.rgb = LINE; line.line.width = Pt(0.8)
    text(s, 0.72, 7.12, 8.0, 0.22, "Institute Intelligence  ·  Case B · The Data Moat  ·  Nextute × Finance Club IIT Patna",
         7.8, False, SLATE, space=0)
    text(s, 11.9, 7.12, 0.7, 0.22, f"{n:02d}", 8, True, BLUE, align=PP_ALIGN.RIGHT, space=0)
    if source:
        text(s, 0.72, 6.82, 11.8, 0.2, source, 7.2, False, MUTED, space=0)


def pill(s, x, y, w, value, fill=PALE, color=BLUE, size=9.5):
    rect(s, x, y, w, 0.34, fill, None)
    text(s, x + 0.13, y + 0.07, w - 0.2, 0.2, value, size, True, color, space=0)


def card(s, x, y, w, h, label, value, note, accent=BLUE, fill=WHITE):
    rect(s, x, y, w, h, fill, LINE)
    text(s, x + 0.22, y + 0.2, w - 0.4, 0.24, label.upper(), 8.5, True, SLATE, space=0)
    text(s, x + 0.22, y + 0.48, w - 0.4, 0.58, value, 24, True, accent, space=0)
    text(s, x + 0.22, y + h - 0.52, w - 0.4, 0.35, note, 8.8, False, SLATE, space=0)


def image(s, filename, x, y, w, border=LINE):
    pic = s.shapes.add_picture(str(ASSETS / filename), Inches(x), Inches(y), width=Inches(w))
    # border on top
    b = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, pic.left, pic.top, pic.width, pic.height)
    b.fill.background(); b.line.color.rgb = border; b.line.width = Pt(1)
    b.shadow.inherit = False
    return pic


def table(s, x, y, w, rows, col_widths, header_fill=NAVY, font_size=10, row_h=0.36):
    nrows, ncols = len(rows), len(rows[0])
    shape = s.shapes.add_table(nrows, ncols, Inches(x), Inches(y), Inches(w), Inches(row_h * nrows))
    tbl = shape.table
    total = sum(col_widths)
    for i, cw in enumerate(col_widths):
        tbl.columns[i].width = Inches(w * cw / total)
    for r in range(nrows):
        tbl.rows[r].height = Inches(row_h)
        for c in range(ncols):
            cell = tbl.cell(r, c)
            cell.text = str(rows[r][c])
            cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if r == 0 else (WHITE if r % 2 else RGBColor(0xF8,0xFA,0xFC))
            for p in cell.text_frame.paragraphs:
                p.space_after = Pt(0)
                for run in p.runs:
                    run.font.name = FONT
                    run.font.size = Pt(font_size)
                    run.font.bold = (r == 0)
                    run.font.color.rgb = WHITE if r == 0 else INK


def notes(s, value):
    s.notes_slide.notes_text_frame.text = value


# 1 — title
s = new_slide(NAVY)
rect(s, 0, 0, 0.16, 7.5, BLUE, None, radius=False)
text(s, 0.72, 0.68, 6.6, 0.3, "CASE B  ·  THE DATA MOAT", 10.5, True, RGBColor(0x93,0xC5,0xFD), space=0)
text(s, 0.72, 1.55, 6.4, 1.9, "The data is\nalready there.\nThe warning is not.", 39, True, WHITE, space=0, line_spacing=0.96)
text(s, 0.75, 3.82, 5.8, 0.92, "A privacy-first analytics layer that turns scattered test, attendance and fee data into timely action for Tier-2 coaching institutes.",
     14.5, False, RGBColor(0xCB,0xD5,0xE1), space=5, line_spacing=1.1)
pill(s, 0.75, 5.18, 2.05, "NEET-first · Patna", NAVY2, RGBColor(0x93,0xC5,0xFD))
pill(s, 2.95, 5.18, 2.55, "Rasch + calibrated risk", NAVY2, RGBColor(0x93,0xC5,0xFD))
pill(s, 5.65, 5.18, 1.95, "DPDP-ready pilot", NAVY2, RGBColor(0x93,0xC5,0xFD))
text(s, 0.75, 6.55, 7.0, 0.35, "Nextute × Finance Club IIT Patna  ·  2026", 10.5, False, RGBColor(0x94,0xA3,0xB8), space=0)
# image card
rect(s, 7.28, 1.3, 5.42, 4.35, NAVY2, RGBColor(0x33,0x41,0x55))
image(s, "dashboard.png", 7.46, 1.48, 5.06, RGBColor(0x33,0x41,0x55))
text(s, 7.46, 6.06, 5.06, 0.3, "Live prototype · Patna NEET Academy", 8.5, False, RGBColor(0x94,0xA3,0xB8), space=0)
text(s, 7.46, 6.3, 5.06, 0.3, "1,000 students · 181k responses · 3 institutes", 8.5, True, RGBColor(0x93,0xC5,0xFD), space=0)
notes(s, "Open on the problem, not the tech. We are not building another LMS. We are turning data the institute already has into a weekly action loop. The prototype on the right is live on synthetic pilot data.")

# 2 — problem
s = new_slide()
kicker(s, "The problem")
title(s, "Coaching institutes are flying blind at the moment it matters.", "The signals exist. They are trapped in OMR sheets, Excel files and WhatsApp threads.")
cards = [
    ("01  Signals are fragmented", "Tests, attendance and fees live in three to five disconnected tools. No one joins them at the student level.", RED),
    ("02  Action arrives late", "Owners see dropout after attendance collapses. Teachers cannot see which topic needs reteaching this week.", AMBER),
    ("03  Parents get a rank", "A percentile without a reason or a next step creates anxiety, not trust — and does not retain the student.", BLUE),
]
for i, (label, body, accent) in enumerate(cards):
    x = 0.72 + i * 4.06
    rect(s, x, 2.25, 3.78, 2.55, WHITE, LINE)
    rect(s, x, 2.25, 0.07, 2.55, accent, None, radius=False)
    text(s, x + 0.28, 2.47, 3.2, 0.28, label.upper(), 9.5, True, accent, space=0)
    text(s, x + 0.28, 2.87, 3.15, 1.55, body, 12.5, False, INK, space=6, line_spacing=1.15)
# bottom
rect(s, 0.72, 5.22, 11.9, 0.92, PALE, None)
text(s, 0.98, 5.42, 11.35, 0.55, "The moat is not more content. It is the workflow that turns existing data into timely, explainable action.",
     15, True, NAVY, space=0)
footer(s, 2, "Problem framing from the case brief; no vendor-specific claims.")

# 3 — loop
s = new_slide()
kicker(s, "The product loop")
title(s, "One weekly loop: measure, explain, act.", "Every score is traceable to a feature. Every parent report is traceable to locked facts.")
steps = [
    ("1", "INGEST", "CSV / Google Forms export", "Validate, quarantine, commit. Idempotent jobs."),
    ("2", "MEASURE", "Rasch ability + topic mastery", "Shrinkage, recency, anchor items."),
    ("3", "EXPLAIN", "Three risk targets + reasons", "Calibrated disengagement; transparent rules."),
    ("4", "ACT", "Intervention + parent report", "Teacher action, EN/HI report, WhatsApp queue."),
]
for i, (num, head, sub, body) in enumerate(steps):
    x = 0.72 + i * 3.03
    rect(s, x, 2.32, 2.74, 2.62, WHITE, LINE)
    text(s, x + 0.22, 2.5, 0.5, 0.45, num, 24, True, BLUE, space=0)
    text(s, x + 0.22, 2.98, 2.3, 0.26, head, 10, True, NAVY, space=0)
    text(s, x + 0.22, 3.28, 2.28, 0.5, sub, 11.2, True, BLUE, space=0, line_spacing=1.0)
    text(s, x + 0.22, 3.85, 2.25, 0.85, body, 9.6, False, SLATE, space=0, line_spacing=1.1)
    if i < 3:
        text(s, x + 2.72, 3.42, 0.35, 0.3, "›", 25, True, RGBColor(0xBF,0xDB,0xFE), space=0)
# bottom stats
for i, (v, l) in enumerate([("28 days", "disengagement horizon"), ("3", "risk targets, separate thresholds"), ("2", "languages, one locked facts object")]):
    x = 0.72 + i * 4.02
    text(s, x, 5.5, 1.4, 0.45, v, 23, True, BLUE, space=0)
    text(s, x, 5.96, 3.1, 0.28, l, 9.5, False, SLATE, space=0)
footer(s, 3, "All outputs are decision support; no student-facing risk labels.")

# 4 — dashboard
s = new_slide()
kicker(s, "The product")
title(s, "Know who is slipping, and why.", "A daily command centre for the owner, with reasons a teacher can act on.")
bullets = [
    ("Three targets, three thresholds", "Disengagement, falling behind, fee default. Fee data is redacted for teachers."),
    ("Rasch, not raw percentages", "Topic mastery with uncertainty and low-evidence labels."),
    ("From flag to action", "Interventions are teacher-owned and audited."),
]
y = 2.2
for head, body in bullets:
    rect(s, 0.72, y + 0.03, 0.11, 0.11, BLUE, None, radius=False)
    text(s, 0.98, y - 0.04, 4.25, 0.3, head, 12.5, True, NAVY, space=0)
    text(s, 0.98, y + 0.3, 4.25, 0.62, body, 9.8, False, SLATE, space=0, line_spacing=1.12)
    y += 1.28
pill(s, 0.98, 6.1, 1.6, "Explainable by default", PALE, BLUE, 8.5)
image(s, "dashboard.png", 5.48, 1.68, 7.12)
footer(s, 4, "Screenshot: synthetic Patna NEET Academy. 400 students.")

# 5 — import
s = new_slide()
kicker(s, "Data in")
title(s, "From 1,205 messy rows to 1,200 usable responses.", "A bad row becomes a visible exception — not a silent analytics failure.")
values = [("1,205", "rows uploaded", BLUE), ("1,200", "accepted", GREEN), ("4", "quarantined", AMBER), ("1", "duplicate", SLATE)]
for i, (v, l, c) in enumerate(values):
    x = 0.72 + i * 2.08
    card(s, x, 2.0, 1.9, 1.18, l, v, "", c)
text(s, 0.72, 3.55, 5.3, 0.3, "WHAT THE PARSER CHECKS", 9.5, True, BLUE, space=0)
checks = "Required columns  ·  topic code  ·  answer key  ·  date format\nquestion range  ·  duplicate rows  ·  test/batch consistency"
text(s, 0.72, 3.9, 5.4, 0.8, checks, 11, False, INK, space=3, line_spacing=1.2)
rect(s, 0.72, 4.95, 5.3, 0.95, PALE, None)
text(s, 0.95, 5.14, 4.9, 0.58, "Review quarantined rows first. Commit only valid rows. Re-upload returns the same job.",
     10.5, True, NAVY, space=0)
image(s, "import.png", 6.05, 1.78, 6.55)
footer(s, 5, "Demo import: 40 students × 30 questions + 5 intentionally bad rows.")

# 6 — student
s = new_slide()
kicker(s, "Teacher view")
title(s, "A student view a teacher can act on.", "Mastery, trend and risk reasons on one page — with the next step attached.")
image(s, "student.png", 0.72, 1.8, 6.65)
items = [
    ("Topic mastery with evidence", "Shrinkage + recency; low-evidence topics are flagged, not over-interpreted."),
    ("Three risk reasons", "Attendance trend, score delta, fees where permitted. No black box."),
    ("Study plan", "Three weakest topics retrieve curated concept and drill briefs."),
    ("Intervention", "Mentoring, remedial, parent call or fee-plan review — audited."),
]
y = 1.88
for head, body in items:
    text(s, 7.62, y, 4.95, 0.28, head, 11.5, True, NAVY, space=0)
    text(s, 7.62, y + 0.3, 4.95, 0.6, body, 9.7, False, SLATE, space=0, line_spacing=1.12)
    y += 1.12
pill(s, 7.62, 6.46, 1.55, "No rank labels", PALE, BLUE, 8.5)
footer(s, 6, "Screenshot: synthetic student record. Teacher fee redaction is enforced server-side and in the template.")

# 7 — parent
s = new_slide()
kicker(s, "Parent view")
title(s, "A parent report that explains, not ranks.", "Attendance, score, strong topics, focus topics and an internal percentile band.")
image(s, "report.png", 6.52, 1.72, 6.12)
text(s, 0.72, 2.02, 5.3, 0.3, "WHAT IS LOCKED", 9.5, True, BLUE, space=0)
lines = [
    ("Fact object", "Every number in the report comes from the facts object. A validator rejects anything else."),
    ("English + Hindi", "Same facts, reviewed template, deterministic fallback."),
    ("No risk. No fees.", "Parents never see dropout labels or fee status."),
    ("90-day link", "Token stored as SHA-256; consent required before creation."),
]
y = 2.38
for head, body in lines:
    text(s, 0.72, y, 5.4, 0.27, head, 11.5, True, NAVY, space=0)
    text(s, 0.72, y + 0.29, 5.4, 0.55, body, 9.6, False, SLATE, space=0, line_spacing=1.1)
    y += 1.02
pill(s, 0.72, 6.55, 1.45, "Fact-locked", RGBColor(0xDC,0xFC,0xE7), GREEN, 8.5)
pill(s, 2.28, 6.55, 1.55, "Bilingual", PALE, BLUE, 8.5)
pill(s, 3.94, 6.55, 1.9, "No exam rank", RGBColor(0xFE,0xF3,0xC7), RGBColor(0x92,0x40,0x0E), 8.5)
footer(s, 7, "Screenshot: synthetic report. The optional LLM path is off; template is the fallback.")

# 8 — AI/ML
s = new_slide()
kicker(s, "AI / ML design")
title(s, "AI where it earns its place.", "Explainable statistics first. Learned models where the data supports them. Rules where it does not.")
quad = [
    ("MEASURE", "Rasch / 1PL", "Ability and item difficulty from response patterns. Empirical-Bayes shrinkage (κ=8), 120-day half-life, 10 anchor items per test.", BLUE),
    ("PREDICT", "Calibrated disengagement", "Logistic model on attendance, score and mastery features. 60/20/20 split, Platt scaling, top-10% review.", GREEN),
    ("BE HONEST", "Rules for thin outcomes", "Fee default and falling behind are transparent v1 rules, labelled as rules in the model card.", AMBER),
    ("COMMUNICATE", "Locked facts + RAG-lite", "Template-first report; every number validated. Study plans retrieve curated topic briefs. No student data to an external model.", RGBColor(0x7C,0x3A,0xED)),
]
for i, (tag, head, body, accent) in enumerate(quad):
    x = 0.72 + (i % 2) * 6.03
    y = 1.95 + (i // 2) * 2.05
    rect(s, x, y, 5.75, 1.82, WHITE, LINE)
    rect(s, x, y, 0.07, 1.82, accent, None, radius=False)
    text(s, x + 0.25, y + 0.18, 1.1, 0.2, tag, 8, True, accent, space=0)
    text(s, x + 0.25, y + 0.43, 5.2, 0.28, head, 14, True, NAVY, space=0)
    text(s, x + 0.25, y + 0.8, 5.2, 0.85, body, 9.4, False, SLATE, space=0, line_spacing=1.12)
rect(s, 0.72, 6.18, 11.9, 0.44, NAVY, None)
text(s, 0.95, 6.28, 11.4, 0.24, "No student-facing chatbot   ·   No invented numbers   ·   No black-box exam rank", 9.5, True, WHITE, space=0)
footer(s, 8, "Model details and failure modes: validation report, sections 4 and 7.")

# 9 — validation
s = new_slide()
kicker(s, "Validation")
title(s, "Validated on a 1,000-student synthetic pilot.", "Enough to test the plumbing and the workflow. Not enough to claim real-world prediction.")
rows = [
    ["Institute", "AUC", "PR-AUC", "80% coverage", "MAE"],
    ["Patna NEET Academy", "0.992", "0.925", "90.0%", "8.07"],
    ["Gaya Success Point", "1.000", "1.000", "74.3%", "8.38"],
    ["Patna JEE Circle", "0.922", "0.738", "84.0%", "8.47"],
]
table(s, 0.72, 2.02, 7.55, rows, [2.4, 1.0, 1.0, 1.3, 0.9], font_size=10.5, row_h=0.44)
text(s, 0.72, 4.12, 7.5, 0.28, "181,201 responses  ·  Rasch converges in 41–76 iterations  ·  6/6 automated tests pass", 9.2, True, SLATE, space=0)
rect(s, 8.62, 2.02, 4.0, 2.5, RGBColor(0xFE,0xF3,0xC7), None)
text(s, 8.86, 2.22, 3.55, 0.28, "READ THIS BEFORE THE AUC", 9, True, RGBColor(0x92,0x40,0x0E), space=0)
text(s, 8.86, 2.58, 3.5, 1.75, "Withdrawal is generated from attendance and fee behaviour. The model partly learns the generator. AUC 1.0 is not a real-world claim.",
     10.4, False, RGBColor(0x78,0x35,0x0F), space=5, line_spacing=1.12)
text(s, 0.72, 4.75, 7.55, 0.45, "What this proves", 12, True, GREEN, space=0)
text(s, 0.72, 5.05, 7.55, 0.55, "Ingestion, fitting, calibration, reporting and privacy controls work end to end — and the analytics rebuild takes 7.7 s.",
     9.8, False, SLATE, space=0, line_spacing=1.12)
text(s, 0.72, 5.72, 7.55, 0.45, "What it does not prove", 12, True, RED, space=0)
text(s, 0.72, 6.02, 7.55, 0.55, "That the model predicts real dropout. The next study is time-based, on consented pilot data, with a pre-registered success bar.",
     9.8, False, SLATE, space=0, line_spacing=1.12)
footer(s, 9, "Synthetic data, seed 20260401. Metrics are held-out splits; Gaya's perfect AUC is a synthetic artefact.")

# 10 — privacy
s = new_slide()
kicker(s, "Privacy by architecture")
title(s, "Privacy is the architecture, not a policy page.", "The parent view, the teacher view and the tenant boundary are different products.")
# left diagram
rect(s, 0.72, 1.9, 6.15, 4.28, RGBColor(0xF8,0xFA,0xFC), LINE)
text(s, 0.98, 2.1, 5.5, 0.28, "INSTITUTE TENANT  ·  RLS FORCED", 8.5, True, BLUE, space=0)
rect(s, 0.98, 2.48, 2.35, 1.22, WHITE, LINE)
text(s, 1.16, 2.62, 1.95, 0.24, "student_pii", 10, True, NAVY, space=0)
text(s, 1.16, 2.91, 1.95, 0.65, "Names, DOB, guardian phone HMAC. Split from operational tables.", 7.8, False, SLATE, space=0)
rect(s, 3.55, 2.48, 2.35, 1.22, WHITE, LINE)
text(s, 3.73, 2.62, 1.95, 0.24, "responses + snapshots", 10, True, NAVY, space=0)
text(s, 3.73, 2.91, 1.95, 0.65, "Item-level data, mastery, risk, percentile bands. Versioned.", 7.8, False, SLATE, space=0)
rect(s, 0.98, 3.97, 2.35, 1.15, WHITE, LINE)
text(s, 1.16, 4.11, 1.95, 0.24, "consent + audit", 10, True, NAVY, space=0)
text(s, 1.16, 4.4, 1.95, 0.6, "Purpose-bound consent; every send, report and erasure logged.", 7.8, False, SLATE, space=0)
rect(s, 3.55, 3.97, 2.35, 1.15, WHITE, LINE)
text(s, 3.73, 4.11, 1.95, 0.24, "job queue", 10, True, NAVY, space=0)
text(s, 3.73, 4.4, 1.95, 0.6, "SECURITY DEFINER functions; no direct app role access.", 7.8, False, SLATE, space=0)
text(s, 0.98, 5.45, 5.5, 0.3, "No tenant context  →  0 rows returned.", 10.5, True, BLUE, space=0)
# right controls
text(s, 7.2, 2.02, 5.2, 0.28, "CONTROLS THAT SHIP IN THE PILOT", 9.5, True, BLUE, space=0)
controls = [
    ("Tenant isolation", "RLS forced on every tenant table; no-context reads return zero."),
    ("Role redaction", "Teacher never sees fee amounts or fee-default risk. Parent never sees risk."),
    ("Consent gate", "Report, link and WhatsApp blocked if parent communication consent is withdrawn."),
    ("Erasure workflow", "Verified request, 30-day execution, audit trail."),
]
y = 2.42
for head, body in controls:
    text(s, 7.2, y, 5.2, 0.27, head, 11.3, True, NAVY, space=0)
    text(s, 7.2, y + 0.29, 5.2, 0.55, body, 9.5, False, SLATE, space=0, line_spacing=1.1)
    y += 0.95
footer(s, 10, "Security is pilot-grade. Production needs DPA, notice review, pen test and provider integration.")

# 11 — market
s = new_slide()
kicker(s, "Market")
title(s, "A large, under-served market — with a narrow wedge.", "Bottom-up, not a top-down TAM slide. Every number is an assumption to test.")
# funnel bars
bars = [
    ("TOTAL COACHING INSTITUTES", "1,20,000", 11.7, RGBColor(0xDB,0xEA,0xFE), NAVY),
    ("NEET / JEE-FOCUSED (25%)", "30,000", 8.9, RGBColor(0xBF,0xDB,0xFE), NAVY),
    ("TIER-2/3, 150+ STUDENTS (40%)", "12,000", 6.2, RGBColor(0x93,0xC5,0xFD), NAVY),
    ("YEAR-3 TARGET (2.7%)", "320", 3.1, BLUE, WHITE),
]
for i, (label, value, width, fill, color) in enumerate(bars):
    y = 2.05 + i * 0.92
    rect(s, 0.72, y, width, 0.62, fill, None)
    text(s, 0.95, y + 0.14, width - 0.4, 0.24, label, 8.2, True, color, space=0)
    text(s, 10.1 if i < 3 else 3.5, y + 0.12, 1.3, 0.3, value, 14, True, color if i < 3 else WHITE, space=0)
# right note
rect(s, 8.2, 2.05, 4.4, 2.55, PALE, None)
text(s, 8.45, 2.25, 3.9, 0.28, "WHY PATNA FIRST", 9, True, BLUE, space=0)
text(s, 8.45, 2.58, 3.9, 1.8, "Dense Tier-2 coaching cluster. Owner-led buying. Hindi + English parent communication. Short feedback loop for a design-partner cohort.",
     10, False, INK, space=4, line_spacing=1.12)
text(s, 0.72, 5.95, 7.4, 0.35, "SAM = 12,000 institutes × blended ACV ₹1.0–1.1L ≈ ₹1,200–1,300 Cr", 10.2, True, NAVY, space=0)
text(s, 0.72, 6.3, 11.4, 0.35, "TAM/SAM are planning assumptions, not verified market research. Validate institute counts, willingness to pay and churn in the pilot.",
     8, False, SLATE, space=0)
footer(s, 11, "Market sizing is explicitly assumption-led; the pilot is the evidence plan.")

# 12 — business
s = new_slide()
kicker(s, "Business model")
title(s, "Unit economics work at ₹35–₹55 per student per month.", "Annual contracts, 10 billed months, 150-student floor. Growth tier is the target mix.")
metrics = [
    ("GROWTH ACV", "₹1.93L", "350 students × ₹55 × 10 months", BLUE),
    ("CONTRIBUTION", "65.3%", "After cloud, support, onboarding, messaging", GREEN),
    ("CAC", "₹38k", "Founder-led sales + onboarding", NAVY),
    ("PAYBACK", "3.6 mo", "Growth tier; 6.6 mo blended", BLUE),
    ("LTV / CAC", "4.6×", "30-month conservative life", GREEN),
    ("BREAK-EVEN", "~110", "Institutes at Year-1 fixed cost", AMBER),
]
for i, (label, value, note, accent) in enumerate(metrics):
    x = 0.72 + (i % 3) * 4.02
    y = 1.92 + (i // 3) * 1.72
    card(s, x, y, 3.74, 1.46, label, value, note, accent)
text(s, 0.72, 5.72, 5.4, 0.3, "PRICE LADDER", 9.5, True, BLUE, space=0)
text(s, 0.72, 6.02, 11.8, 0.3, "Starter ₹35  ·  200 students  ·  ACV ₹70k          Growth ₹55  ·  350 students  ·  ACV ₹1.93L          10 billed months  ·  ₹1.0Cr ask",
     11.5, True, NAVY, space=0)
text(s, 0.72, 6.38, 11.8, 0.3, "Service cost per institute: ₹25k Starter / ₹66.7k Growth. Fixed costs: ₹76L Year 1 → ₹1.2Cr Year 3.",
     8.5, False, SLATE, space=0)
footer(s, 12, "Full model: docs/institute_intelligence_financial_model.xlsx. Assumptions are editable.")

# 13 — roadmap
s = new_slide()
kicker(s, "Go-to-market")
title(s, "Wedge → proof → scale.", "Sell the weekly workflow to owners. Prove retention and parent engagement. Expand by referral.")
# timeline
line = s.shapes.add_connector(1, Inches(0.95), Inches(3.02), Inches(12.2), Inches(3.02))
line.line.color.rgb = RGBColor(0xBF,0xDB,0xFE); line.line.width = Pt(3)
phases = [
    ("NOW", "3 synthetic institutes", "Working prototype; 181k responses; 6/6 tests.", 0.95, BLUE),
    ("NEXT 90 DAYS", "10 design partners", "2 paid pilots; 300–600 students; parent report study.", 3.75, BLUE),
    ("YEAR 1", "40 institutes", "≈9,500 students; native Forms; OMR adapter.", 6.55, BLUE),
    ("YEAR 2–3", "140 → 320 institutes", "34k → 80k students; UP/Jharkhand; benchmark network.", 9.35, GREEN),
]
for label, head, body, x, accent in phases:
    rect(s, x, 2.72, 0.55, 0.55, accent, None)
    text(s, x + 0.05, 2.85, 0.45, 0.25, "●", 11, True, WHITE, align=PP_ALIGN.CENTER, space=0)
    text(s, x, 3.38, 2.55, 0.25, label, 8.5, True, accent, space=0)
    text(s, x, 3.68, 2.55, 0.55, head, 13, True, NAVY, space=0)
    text(s, x, 4.28, 2.55, 1.3, body, 8.9, False, SLATE, space=0, line_spacing=1.12)
# bottom ask / allocation
rect(s, 0.72, 5.72, 5.35, 0.88, NAVY, None)
text(s, 0.95, 5.88, 4.9, 0.25, "ASK  ·  ₹1.0 CRORE / 18 MONTHS", 9, True, RGBColor(0x93,0xC5,0xFD), space=0)
text(s, 0.95, 6.14, 4.9, 0.3, "Product 35% · pilots 20% · sales 20% · content/compliance 15% · buffer 10%", 8.4, False, WHITE, space=0)
text(s, 6.35, 5.82, 6.2, 0.3, "Milestones that unlock the next round", 9, True, BLUE, space=0)
text(s, 6.35, 6.14, 6.2, 0.55, "10 paying institutes · 60%+ parent report open rate · 3-point attendance lift · CAC payback under 9 months",
     9.2, False, SLATE, space=0, line_spacing=1.1)
footer(s, 13, "Plan is a hypothesis set; each phase has a kill/scale gate.")

# 14 — close
s = new_slide(NAVY)
rect(s, 0, 0, 13.333, 0.12, BLUE, None, radius=False)
text(s, 0.72, 0.7, 6.0, 0.3, "THE MOAT", 10.5, True, RGBColor(0x93,0xC5,0xFD), space=0)
text(s, 0.72, 1.55, 11.2, 1.65, "Start with 10 Patna institutes.\nBuild the trust layer for Indian coaching.", 35, True, WHITE, space=0, line_spacing=1.0)
proofs = [
    ("1,000", "students in the synthetic pilot"),
    ("181k", "responses through the full pipeline"),
    ("6/6", "automated tests passing"),
]
for i, (v, l) in enumerate(proofs):
    x = 0.72 + i * 3.2
    text(s, x, 3.85, 2.4, 0.55, v, 28, True, RGBColor(0x93,0xC5,0xFD), space=0)
    text(s, x, 4.42, 2.6, 0.3, l, 9, False, RGBColor(0xCB,0xD5,0xE1), space=0)
text(s, 0.72, 5.42, 8.4, 0.65, "The moat is the weekly workflow — and the permission to act on it.",
     18, True, WHITE, space=0)
text(s, 0.72, 6.55, 8.0, 0.3, "Nextute × Finance Club IIT Patna  ·  Case B · 2026", 9.5, False, RGBColor(0x94,0xA3,0xB8), space=0)
rect(s, 9.35, 5.2, 3.25, 1.35, NAVY2, RGBColor(0x33,0x41,0x55))
text(s, 9.58, 5.38, 2.8, 0.25, "DEMO LOGIN", 8.5, True, RGBColor(0x93,0xC5,0xFD), space=0)
text(s, 9.58, 5.66, 2.8, 0.65, "owner@demo.test\ndemo1234", 10.5, True, WHITE, space=0)
notes(s, "Close on trust and execution. We are not claiming a validated dropout model yet. We are claiming a working workflow, honest metrics and a clear pilot plan.")

out = ROOT / "docs" / "03_pitch_deck.pptx"
prs.save(out)
print(f"saved {out} ({len(prs.slides)} slides)")
