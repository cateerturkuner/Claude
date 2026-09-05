"""Generate the monthly actuals workbook for a venue.

    python3 tools/make_actuals_template.py hadden_estate [out.xlsx]

Produces the file finance fills in each month. The layout is the one the
dashboard's parser expects, so a completed copy uploads without any mapping
work: month columns across, model line names down, and a separate event list
for attachment.
"""
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from postclose import analysis, store  # noqa: E402

TEAL = "12666B"
TEAL_LIGHT = "E8F4F5"
NAVY = "1A365D"
GREY = "718096"
INPUT_FILL = "FFFDF6E8"

H1 = Font(name="Calibri", size=14, bold=True, color=NAVY)
H2 = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
GROUP = Font(name="Calibri", size=9, bold=True, color=TEAL)
LABEL = Font(name="Calibri", size=10)
LABEL_B = Font(name="Calibri", size=10, bold=True, color=NAVY)
NOTE = Font(name="Calibri", size=9, color=GREY, italic=True)

FILL_HEAD = PatternFill("solid", fgColor=TEAL)
FILL_GROUP = PatternFill("solid", fgColor=TEAL_LIGHT)
FILL_INPUT = PatternFill("solid", fgColor="FDF6E3")
THIN = Side(style="thin", color="D9E2EC")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Subtotals the dashboard rebuilds from components. Left out so there is nothing
# to reconcile by hand -- one fewer thing for finance to get wrong.
SKIP = {"lead_to_tour", "tour_to_contract", "events", "total_revenue",
        "total_cogs", "gross_margin", "total_payroll", "total_opex",
        "ebitdar", "ebitda"}

INSTRUCTIONS = [
    ("head", "How to fill this in"),
    ("gap", ""),
    ("body", "1. One column per month. Fill only months that have closed — leave "
             "future months blank."),
    ("body", "2. Money in whole dollars. The dashboard converts; do not pre-scale "
             "to thousands."),
    ("body", "3. Costs as positive numbers. The dashboard flips the sign on import."),
    ("body", "4. Do not add, rename, reorder or delete rows. The line names are how "
             "the dashboard matches them."),
    ("body", "5. Send the whole file each month, not just the new column — it is "
             "the running record."),
    ("gap", ""),
    ("head", "Timing — this is the part that is easy to get wrong"),
    ("body", "Everything is accrual. The revenue and the costs of an event belong "
             "to the month the EVENT HAPPENED,"),
    ("body", "not the month it was booked, invoiced or paid."),
    ("gap", ""),
    ("body", "    Leads          enquiries received in that month"),
    ("body", "    Tours          tours that took place in that month"),
    ("body", "    Contracts      contracts signed in that month, whenever the "
             "event falls"),
    ("body", "    Events         events held in that month — this is where "
             "revenue lands"),
    ("gap", ""),
    ("body", "So the four counts describe different deals and will not tie to each "
             "other. That is intended."),
    ("gap", ""),
    ("head", "The Events sheet"),
    ("body", "One row per event held. Optional, but it is the only way to tell "
             "\"fewer couples bought floral\""),
    ("body", "apart from \"floral sold for less\" — which is most of the value in "
             "this analysis."),
    ("gap", ""),
    ("body", "    · Put the dollar amount in each category the event bought. Leave "
             "blank if they did not buy it."),
    ("body", "    · Contract Type is Original for events inherited at closing, New "
             "for anything sold since."),
    ("body", "    · Each category total should agree with the matching revenue "
             "line on the P&L sheet."),
    ("gap", ""),
    ("head", "Questions"),
    ("body", "If a line on your side has no home here, do not force it into the "
             "nearest row — say so and it gets added."),
]


def build(slug, out_path):
    base = store.baseline(slug)
    months = base["months"]
    lines = [ln for ln in base["lines"] if ln["key"] not in SKIP]

    wb = Workbook()

    # ---- Instructions -----------------------------------------------------
    ws = wb.active
    ws.title = "Instructions"
    ws.sheet_view.showGridLines = False
    ws["B2"] = f"{base['venue']} — Monthly Actuals"
    ws["B2"].font = H1
    ws["B3"] = (f"Closed {base['close_month']}. Post-close Y1 runs "
                f"{analysis.ym_label(months[0]['ym'])} to "
                f"{analysis.ym_label(months[11]['ym'])}.")
    ws["B3"].font = NOTE
    row = 5
    for style, text in INSTRUCTIONS:
        if style == "gap":
            row += 1
            continue
        c = ws.cell(row, 2, text)
        c.font = LABEL_B if style == "head" else LABEL
        row += 1
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions["B"].width = 108

    # ---- P&L --------------------------------------------------------------
    ws = wb.create_sheet("P&L")
    ws.sheet_view.showGridLines = False
    ws["B2"] = f"{base['venue']} — Monthly Actuals"
    ws["B2"].font = H1
    ws["B3"] = "Whole dollars. Costs positive. Fill closed months only."
    ws["B3"].font = NOTE

    head = 5
    ws.cell(head, 2, "Line").font = H2
    ws.cell(head, 2).fill = FILL_HEAD
    ws.cell(head - 1, 2, "Post-close year").font = GROUP
    for i, m in enumerate(months):
        col = 3 + i
        yc = ws.cell(head - 1, col, f"Y{m['post_close_year']}")
        yc.font = GROUP
        yc.alignment = Alignment(horizontal="center")
        yc.fill = FILL_GROUP
        c = ws.cell(head, col, analysis.ym_label(m["ym"]))
        c.font = H2
        c.fill = FILL_HEAD
        c.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(col)].width = 11

    row = head + 1
    group = None
    for ln in lines:
        if ln["group"] != group:
            group = ln["group"]
            gc = ws.cell(row, 2, analysis.GROUP_LABELS.get(group, group).upper())
            gc.font = GROUP
            for col in range(2, 3 + len(months)):
                ws.cell(row, col).fill = FILL_GROUP
            row += 1
        ws.cell(row, 2, ln["label"]).font = LABEL
        for i in range(len(months)):
            c = ws.cell(row, 3 + i)
            c.fill = FILL_INPUT
            c.border = BOX
            c.number_format = "#,##0" if ln["format"] != "count" else "0"
        row += 1

    ws.column_dimensions["A"].width = 2
    ws.column_dimensions["B"].width = 34
    ws.freeze_panes = ws.cell(head + 1, 3)

    # ---- Events -----------------------------------------------------------
    ws = wb.create_sheet("Events")
    ws.sheet_view.showGridLines = False
    ws["B2"] = f"{base['venue']} — Events Held"
    ws["B2"].font = H1
    ws["B3"] = ("One row per event that took place. Dollar amount in each category "
                "the event bought; blank if they did not buy it.")
    ws["B3"].font = NOTE

    cats = [(c["key"], c["label"]) for c in base["drivers"]["categories"]]
    headers = (["Event Date", "Contract Type"] + [label for _, label in cats]
               + ["Service Charge"])
    for i, name in enumerate(headers):
        c = ws.cell(5, 2 + i, name)
        c.font = H2
        c.fill = FILL_HEAD
        c.alignment = Alignment(horizontal="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(2 + i)].width = 15 if i < 2 else 12
    for r in range(6, 406):
        for i in range(len(headers)):
            c = ws.cell(r, 2 + i)
            c.fill = FILL_INPUT
            c.border = BOX
            if i == 0:
                c.number_format = "yyyy-mm-dd"
            elif i > 1:
                c.number_format = "#,##0"
    ws.cell(6, 3).comment = None
    ws.column_dimensions["A"].width = 2
    ws.freeze_panes = ws.cell(6, 4)

    wb.save(out_path)
    return out_path, len(months), len(lines), len(headers)


if __name__ == "__main__":
    slug = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else f"{slug}_actuals_template.xlsx"
    path, n_months, n_lines, n_cols = build(slug, out)
    print(f"{path}: {n_months} month columns, {n_lines} P&L lines, "
          f"{n_cols} event columns")
