from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

NAVY = "0F172A"; BLUE = "1D4ED8"; LIGHT = "EFF6FF"; GRAY = "F1F5F9"
thin = Side(style="thin", color="E2E8F0")
border = Border(left=thin, right=thin, top=thin, bottom=thin)

def title(ws, text, sub=None):
    ws["A1"] = text; ws["A1"].font = Font(size=18, bold=True, color=NAVY)
    if sub:
        ws["A2"] = sub; ws["A2"].font = Font(size=10, color="475569")

def header(ws, row, values):
    for col, v in enumerate(values, start=1):
        c = ws.cell(row=row, column=col, value=v)
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = border

def style_range(ws, r1, r2, c1, c2):
    for row in ws.iter_rows(min_row=r1, max_row=r2, min_col=c1, max_col=c2):
        for c in row:
            c.border = border
            c.alignment = Alignment(vertical="center", wrap_text=True)

wb = Workbook()

# Read me
ws = wb.active; ws.title = "Read me"
ws.column_dimensions["A"].width = 24; ws.column_dimensions["B"].width = 98
title(ws, "Institute Intelligence — 3-year financial model", "Case B · The Data Moat · Nextute × Finance Club IIT Patna 2026")
notes = [
    ("Purpose", "Bottom-up operating model for a Tier-2/3 coaching analytics pilot. Built for assumptions testing, not a forecast."),
    ("Currency", "Indian rupees (INR), nominal. Fiscal year = April–March."),
    ("Pricing", "₹35/student/month (Starter) and ₹55/student/month (Growth); 10 billed months; 150-student floor."),
    ("Revenue", "Recognised revenue uses average institutes in year × blended ACV. ARR uses year-end institutes."),
    ("Costs", "Service cost includes cloud, support, onboarding amortisation, WhatsApp/SMS, payments and content ops."),
    ("Fixed costs", "Team, office, tools, compliance and demand generation. Founder salaries below market in Year 1."),
    ("Caveat", "All demand, churn and pricing assumptions are hypotheses to test with 10 design-partner institutes."),
    ("Sheets", "Assumptions → Unit economics → 3-Year P&L → Break-even → Sensitivity → Use of funds."),
]
for i, (k, v) in enumerate(notes, start=4):
    ws.cell(row=i, column=1, value=k).font = Font(bold=True, color=NAVY)
    ws.cell(row=i, column=2, value=v)
    ws.cell(row=i, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    style_range(ws, i, i, 1, 2)

# Assumptions
ws = wb.create_sheet("Assumptions")
title(ws, "Assumptions", "Edit blue cells; downstream sheets recalculate.")
widths = [38, 18, 18, 18, 18]
for i, w in enumerate(widths, start=1): ws.column_dimensions[get_column_letter(i)].width = w
header(ws, 4, ["Driver", "Starter", "Growth", "Blended Y1", "Notes"])
assumptions = [
    ("Price per student per month (₹)", 35, 55, "", "Willingness-to-pay hypothesis"),
    ("Billed months per year", 10, 10, "", "April–January; Feb–Mar free"),
    ("Average students per institute", 200, 350, "", "Growth tier assumes 350"),
    ("Annual contract value (₹)", "=B5*B6*B7", "=C5*C6*C7", "", "Price × months × students"),
    ("Service cost per institute / year (₹)", 25000, 66730, "", "Cloud, support, onboarding, messaging"),
    ("Contribution per institute / year (₹)", "=B8-B9", "=C8-C9", "", "ACV minus service cost"),
    ("Contribution margin", "=B10/B8", "=C10/C8", "", "Gross margin before fixed costs"),
]
for r, row in enumerate(assumptions, start=5):
    for c, v in enumerate(row, start=1):
        ws.cell(row=r, column=c, value=v)
        if c in (2, 3) and isinstance(v, (int, float)) or (c in (2,3) and isinstance(v, str) and v.startswith("=")):
            ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=LIGHT)
    ws.cell(row=r, column=1).font = Font(bold=(r in (8, 10)))
ws["B11"].number_format = "0%"; ws["C11"].number_format = "0%"
for c in ("B8", "C8", "B9", "C9", "B10", "C10"):
    ws[c].number_format = '#,##0'

header(ws, 14, ["Mix & scale", "Year 1", "Year 2", "Year 3", "Notes"])
mix = [
    ("Starter share of institutes", 0.75, 0.70, 0.65, "Land small, expand"),
    ("Growth share of institutes", "=1-B15", "=1-C15", "=1-D15", "Residual"),
    ("Blended ACV (₹)", "=B15*$B$8+C15*$C$8", "=C15*$B$8+D15*$C$8", "=D15*$B$8+E15*$C$8", ""),
    ("Blended contribution (₹)", "=B15*$B$10+C15*$C$10", "=C15*$B$10+D15*$C$10", "=D15*$B$10+E15*$C$10", ""),
    ("Year-end institutes", 40, 140, 320, "Sales capacity ramp"),
    ("Average institutes in year", 18, 88, 225, "Lag between adds and revenue"),
    ("Year-end students", "=B19*(B15*$B$7+C15*$C$7)", "=C19*(C15*$B$7+D15*$C$7)", "=D19*(D15*$B$7+E15*$C$7)", ""),
]
for r, row in enumerate(mix, start=15):
    for c, v in enumerate(row, start=1):
        ws.cell(row=r, column=c, value=v)
        if c in (2,3,4) and isinstance(v,(int,float,str)):
            ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=LIGHT)
for c in ("B15","C15","D15","B16","C16","D16"):
    ws[c].number_format = "0%"
for c in ("B17","C17","D17","B18","C18","D18","B21","C21","D21"):
    ws[c].number_format = '#,##0'

header(ws, 23, ["Fixed cost base", "Year 1", "Year 2", "Year 3", "Notes"])
fixed = [
    ("Team (₹)", 4800000, 6000000, 7800000, "5–9 people; below-market founder pay"),
    ("Demand generation (₹)", 800000, 1200000, 1800000, "Founder-led + referrals"),
    ("Office, tools, cloud (₹)", 900000, 1100000, 1400000, "Lean Patna office"),
    ("Compliance, legal, audit (₹)", 400000, 500000, 700000, "DPDP, contracts, security"),
    ("Content & assessment ops (₹)", 700000, 400000, 300000, "Curated library, item review"),
    ("Total fixed cost (₹)", "=SUM(B24:B28)", "=SUM(C24:C28)", "=SUM(D24:D28)", ""),
]
for r, row in enumerate(fixed, start=24):
    for c, v in enumerate(row, start=1):
        ws.cell(row=r, column=c, value=v)
        if c in (2,3,4) and isinstance(v,(int,float,str)):
            ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=LIGHT)
for c in ("B29","C29","D29"):
    ws[c].number_format = '#,##0'; ws[c].font = Font(bold=True)

# Unit economics
ws = wb.create_sheet("Unit economics")
title(ws, "Unit economics", "One institute, first 12 months.")
ws.column_dimensions["A"].width = 40; ws.column_dimensions["B"].width = 18; ws.column_dimensions["C"].width = 18
header(ws, 4, ["Metric", "Starter", "Growth"])
rows = [
    ("ACV (₹)", "=Assumptions!B8", "=Assumptions!C8"),
    ("Service cost (₹)", "=Assumptions!B9", "=Assumptions!C9"),
    ("Contribution (₹)", "=B5-B6", "=C5-C6"),
    ("Contribution margin", "=B7/B5", "=C7/C5"),
    ("CAC (₹)", 38000, 38000),
    ("CAC payback (months)", "=B9/(B7/12)", "=C9/(C7/12)"),
    ("Average life (months)", 30, 30),
    ("LTV (₹)", "=B7/12*B11", "=C7/12*C11"),
    ("LTV / CAC", "=B12/B9", "=C12/C9"),
]
for r, row in enumerate(rows, start=5):
    for c, v in enumerate(row, start=1):
        ws.cell(row=r, column=c, value=v)
    ws.cell(row=r, column=1).font = Font(bold=(r in (7, 9, 13)))
for c in ("B5","C5","B6","C6","B7","C7","B9","C9","B12","C12"):
    ws[c].number_format = '#,##0'
for c in ("B8","C8"):
    ws[c].number_format = '0.0%'
for c in ("B10","C10","B13","C13"):
    ws[c].number_format = '0.0'

# P&L
ws = wb.create_sheet("3-Year P&L")
title(ws, "3-year P&L", "Revenue recognition uses average institutes; ARR uses year-end.")
ws.column_dimensions["A"].width = 38
for col in "BCD": ws.column_dimensions[col].width = 18
header(ws, 4, ["Line item (₹)", "Year 1", "Year 2", "Year 3"])
pl = [
    ("Starter share", "=Assumptions!B15", "=Assumptions!C15", "=Assumptions!D15"),
    ("Growth share", "=Assumptions!B16", "=Assumptions!C16", "=Assumptions!D16"),
    ("Blended ACV", "=Assumptions!B17", "=Assumptions!C17", "=Assumptions!D17"),
    ("Average institutes", "=Assumptions!B20", "=Assumptions!C20", "=Assumptions!D20"),
    ("Revenue", "=B8*B7", "=C8*C7", "=D8*D7"),
    ("Blended contribution per institute", "=Assumptions!B18", "=Assumptions!C18", "=Assumptions!D18"),
    ("Contribution", "=B8*B10", "=C8*C10", "=D8*D10"),
    ("Service cost", "=B9-B11", "=C9-C11", "=D9-D11"),
    ("Fixed cost", "=Assumptions!B29", "=Assumptions!C29", "=Assumptions!D29"),
    ("EBITDA", "=B11-B13", "=C11-C13", "=D11-D13"),
    ("EBITDA margin", "=B14/B9", "=C14/C9", "=D14/D9"),
    ("Cumulative EBITDA", "=B14", "=B16+C14", "=C16+D14"),
    ("Year-end institutes", "=Assumptions!B19", "=Assumptions!C19", "=Assumptions!D19"),
    ("Year-end students", "=Assumptions!B21", "=Assumptions!C21", "=Assumptions!D21"),
    ("ARR (year-end institutes × ACV)", "=B17*B7", "=C17*C7", "=D17*D7"),
]
for r, row in enumerate(pl, start=5):
    for c, v in enumerate(row, start=1):
        ws.cell(row=r, column=c, value=v)
    ws.cell(row=r, column=1).font = Font(bold=(r in (9, 11, 14, 15, 16)))
for r in range(5, 20):
    for c in (2,3,4):
        cell = ws.cell(row=r, column=c)
        if r in (5,6,15): cell.number_format = '0%'
        elif r in (18,19): cell.number_format = '#,##0'
        else: cell.number_format = '#,##0'
style_range(ws, 4, 19, 1, 4)

# Break-even
ws = wb.create_sheet("Break-even")
title(ws, "Break-even and funding", "Break-even at the Year-1 fixed cost base.")
ws.column_dimensions["A"].width = 44; ws.column_dimensions["B"].width = 22
rows = [
    ("Year-1 fixed cost (₹)", "=Assumptions!B29"),
    ("Blended contribution per institute (Year 2 mix) (₹)", "=Assumptions!C18"),
    ("Break-even institutes", "=B5/B6"),
    ("Growth-tier contribution / month (₹)", "=Assumptions!C10/12"),
    ("Growth-tier CAC payback (months)", "=38000/B8"),
    ("Peak cumulative EBITDA (₹)", "='3-Year P&L'!C16"),
    ("Funding ask (₹)", 10000000),
    ("Runway / buffer (₹)", "=B11+B10"),
]
for r, row in enumerate(rows, start=5):
    for c, v in enumerate(row, start=1):
        ws.cell(row=r, column=c, value=v)
for c in ("B5","B6","B11","B12","B13"): ws[c].number_format = '#,##0'
ws["B8"].number_format = '0.0'; ws["B10"].number_format = '0.0'

# Sensitivity
ws = wb.create_sheet("Sensitivity")
title(ws, "Sensitivity", "Year-3 EBITDA (₹ lakh) vs average institutes and fixed cost.")
ws.column_dimensions["A"].width = 24
for col in "BCDE": ws.column_dimensions[col].width = 16
ws["A4"] = "Average institutes →"; ws["A4"].font = Font(bold=True)
for i, n in enumerate((180, 225, 270), start=2):
    ws.cell(row=4, column=i, value=n)
ws["A5"] = "Fixed cost ↓"; ws["A5"].font = Font(bold=True)
for r, fixed in enumerate((10800000, 12000000, 13200000), start=5):
    ws.cell(row=r, column=1, value=fixed)
    for c, n in enumerate((180, 225, 270), start=2):
        # contribution per institute 73,285; values in lakh
        ws.cell(row=r, column=c, value=f"=({n}*Assumptions!D18-{fixed})/100000")
        ws.cell(row=r, column=c).number_format = '0.0'
for r in range(5,8):
    ws.cell(row=r, column=1).number_format = '#,##0'

# Use of funds
ws = wb.create_sheet("Use of funds")
title(ws, "Use of funds — ₹1.0 crore", "18-month plan to 110+ paying institutes.")
header(ws, 4, ["Category", "Amount (₹)", "Share", "What it buys"])
uses = [
    ("Product & engineering", 3500000, "Two engineers; import/analytics/report hardening, OMR adapter."),
    ("Pilot delivery & onboarding", 2000000, "10 design partners; data cleaning; teacher training."),
    ("Sales & channel", 2000000, "Founder-led sales, local events, referral incentives."),
    ("Content & assessment ops", 1000000, "Curated topic briefs, item review, Hindi QA."),
    ("Compliance, legal, security", 500000, "DPDP notices, DPA, audit, penetration test."),
    ("Working capital & buffer", 1000000, "Receivables, contingency."),
]
for r, (cat, amt, note) in enumerate(uses, start=5):
    ws.cell(row=r, column=1, value=cat)
    ws.cell(row=r, column=2, value=amt).number_format = '#,##0'
    ws.cell(row=r, column=3, value=f"=B{r}/10000000").number_format = '0%'
    ws.cell(row=r, column=4, value=note)
ws.cell(row=11, column=1, value="Total").font = Font(bold=True)
ws.cell(row=11, column=2, value="=SUM(B5:B10)").number_format = '#,##0'
ws.cell(row=11, column=3, value="=SUM(C5:C10)").number_format = '0%'
ws.column_dimensions["A"].width = 34; ws.column_dimensions["B"].width = 16; ws.column_dimensions["C"].width = 10; ws.column_dimensions["D"].width = 70
style_range(ws, 4, 11, 1, 4)

for sheet in wb.worksheets:
    sheet.sheet_view.showGridLines = False

wb.save("docs/institute_intelligence_financial_model.xlsx")
print("saved docs/institute_intelligence_financial_model.xlsx")
