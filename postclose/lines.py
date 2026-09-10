"""The canonical chart of lines, and how workbook labels map onto it.

Venue models are not identical. Hadden ends at EBITDA after a rent line; Firefly
ends at Adjusted EBITDAR after an adjustments block, and carries elopement,
all-inclusive and corporate-payroll lines Hadden has no concept of. Rather than
a row map per workbook, extraction reads the labels in the P&L's own label column
and matches them here, so a new venue only needs a code change when it introduces
a line nobody has used before.

Order is display order. A line absent from a workbook is simply absent from that
venue's baseline.
"""

# key, group, format, labels seen in the wild (first is canonical)
LINE_SPEC = [
    ("leads", "funnel", "count", ["Leads"]),
    ("lead_to_tour", "funnel", "pct", ["L->T Conversion", "Lead to Tour Conversion"]),
    ("tours", "funnel", "count", ["Tours"]),
    ("tour_to_contract", "funnel", "pct", ["T->C Conversion",
                                           "Tour to Contract Conversion"]),
    ("contracts", "funnel", "count", ["Contracts"]),
    ("events_oc", "funnel", "count", ["Original", "Original Contracts"]),
    ("events_new", "funnel", "count", ["New", "New Contracts"]),
    ("events", "funnel", "count", ["Events"]),

    ("room_rental", "revenue", "usd", ["Room Rental Revenue"]),
    ("elopement", "revenue", "usd", ["Elopement Revenue"]),
    ("all_inclusive", "revenue", "usd", ["All Inclusive Revenue"]),
    ("food", "revenue", "usd", ["Food Revenue"]),
    ("beverage", "revenue", "usd", ["Beverage Revenue"]),
    ("lodging", "revenue", "usd", ["Lodging Revenues", "Lodging Revenue"]),
    ("ancillary", "revenue", "usd", ["Ancillary Revenue"]),
    ("service_charge", "revenue", "usd", ["Service Charge"]),
    ("cancelled_events", "revenue", "usd", ["Cancelled Events"]),
    ("outside_events", "revenue", "usd", ["Outside Events"]),
    ("discounts", "revenue", "usd", ["Discounts"]),
    ("other_revenue", "revenue", "usd", ["Other Revenue"]),
    ("total_revenue", "total", "usd", ["Total Revenue"]),

    ("food_cogs", "cogs", "usd", ["Food COGS"]),
    ("ancillary_cogs", "cogs", "usd", ["Ancillary COGS"]),
    ("alcohol_cogs", "cogs", "usd", ["Alcohol COGS"]),
    ("all_inclusive_cogs", "cogs", "usd", ["All Inclusive COGS"]),
    ("other_cogs", "cogs", "usd", ["Other COGS"]),
    ("room_cogs", "cogs", "usd", ["Room COGS"]),
    ("total_cogs", "total", "usd", ["Total COGS"]),
    ("gross_margin", "total", "usd", ["Gross Margin"]),

    ("sales_payroll", "payroll", "usd", ["Sales Team Payroll"]),
    ("planning_payroll", "payroll", "usd", ["Planning Team Payroll"]),
    ("operations_payroll", "payroll", "usd", ["Operations Team Payroll"]),
    ("ancillary_payroll", "payroll", "usd", ["Ancillary Payroll"]),
    ("corporate_payroll", "payroll", "usd", ["Corporate Team Payroll"]),
    ("fnb_payroll", "payroll", "usd", ["F&B Team Payroll"]),
    ("owner_salaries", "payroll", "usd", ["Owner Salaries"]),
    ("payroll_admin", "payroll", "usd", ["Payroll Admin & Benefit Expenses"]),
    ("other_payroll", "payroll", "usd", ["Other Payroll"]),
    ("total_payroll", "total", "usd", ["Total Payroll"]),

    ("marketing", "opex", "usd", ["Marketing Expense"]),
    ("maintenance", "opex", "usd", ["Maintenance Expense"]),
    ("utilities", "opex", "usd", ["Utilities Expense"]),
    ("office", "opex", "usd", ["Office Expense"]),
    ("computer", "opex", "usd", ["Computer Expense"]),
    ("automobile", "opex", "usd", ["Automobile Expenses"]),
    ("training", "opex", "usd", ["Training & Development Expense"]),
    ("tax", "opex", "usd", ["Tax Expense"]),
    ("travel", "opex", "usd", ["Travel Expense"]),
    ("professional", "opex", "usd", ["Professional Expenses"]),
    ("rent_expense", "opex", "usd", ["Rent Expense"]),
    ("insurance", "opex", "usd", ["Insurance"]),
    ("finance", "opex", "usd", ["Finance Expenses"]),
    ("personal", "opex", "usd", ["Personal Expenses"]),
    ("other_opex", "opex", "usd", ["Other Operating Expenses"]),
    ("total_opex", "total", "usd", ["Total Operating Expenses"]),

    ("ebitdar", "total", "usd", ["EBITDAR"]),
    ("rent", "total", "usd", ["Rent"]),
    ("ebitda", "total", "usd", ["EBITDA"]),

    ("addback_rent", "adjust", "usd", ["Addback: Rent"]),
    ("addback_personal", "adjust", "usd", ["Addback: Personal Expenses"]),
    ("addback_owner_payroll", "adjust", "usd", ["Addback: Owner Payroll"]),
    ("less_annualizing_comp", "adjust", "usd",
     ["Less: Annuallzing Comp", "Less: Annualizing Comp"]),
    ("total_other_adj", "total", "usd", ["Total Other Adj."]),
    ("adjusted_ebitdar", "total", "usd", ["Adjusted EBITDAR"]),
]

BY_KEY = {key: {"key": key, "group": group, "format": fmt, "label": labels[0]}
          for key, group, fmt, labels in LINE_SPEC}
ORDER = [key for key, _, _, _ in LINE_SPEC]

# Subtotals, in dependency order, expressed as (key, group to sum) or
# (key, [component keys]). Applied only where the components exist.
SUBTOTAL_GROUPS = [
    ("total_revenue", "revenue"),
    ("total_cogs", "cogs"),
    ("total_payroll", "payroll"),
    ("total_opex", "opex"),
    ("total_other_adj", "adjust"),
]
SUBTOTAL_SUMS = [
    ("events", ["events_oc", "events_new"]),
    ("gross_margin", ["total_revenue", "total_cogs"]),
    ("ebitdar", ["gross_margin", "total_payroll", "total_opex"]),
    ("ebitda", ["ebitdar", "rent"]),
    ("adjusted_ebitdar", ["ebitdar", "total_other_adj"]),
]

# The comparison line. EBITDAR first, deliberately: rent is negotiated per deal
# and is not always underwritten -- Hadden's proforma carries it, Firefly's does
# not -- so comparing before rent is the only basis that holds across venues.
# Rent and the lines below it are still shown where a venue has them.
PROFIT_PREFERENCE = ["ebitdar", "adjusted_ebitdar", "ebitda"]

# Section headers in the label column. They mark a group boundary rather than a
# line, so they are skipped rather than matched.
SECTION_HEADERS = {"revenue", "cogs", "payroll", "operating expenses",
                   "other adjustments", "seasonality", "checks"}


def normalise(text):
    if text is None:
        return ""
    return " ".join(str(text).replace("&", "&").split()).strip().lower()


LABEL_INDEX = {}
for _key, _group, _fmt, _labels in LINE_SPEC:
    for _label in _labels:
        LABEL_INDEX.setdefault(normalise(_label), _key)


# Revenue that can sensibly be reported one event at a time, and therefore comes
# from the Events sheet rather than being asked for again on the P&L sheet.
# Anything not listed here -- cancellations, discounts, other income -- is not an
# event-level number and stays on the P&L sheet.
EVENT_REVENUE_LINES = {
    "room_rental": ["room_rental"],
    "elopement": ["elopement"],
    "all_inclusive": ["all_inclusive"],
    "food": ["food"],
    "beverage": ["beverage"],
    "lodging": ["lodging"],
    "service_charge": ["service_charge"],
    "ancillary": ["dj", "floral", "bakery", "stationery", "photography",
                  "other_ancillary"],
}

# The six ancillary categories are reported per category on the Events sheet but
# land on a single Ancillary Revenue line in the P&L.
ANCILLARY_CATEGORIES = EVENT_REVENUE_LINES["ancillary"]

CATEGORY_LABELS = {
    "room_rental": "Room Rental", "elopement": "Elopement",
    "all_inclusive": "All Inclusive", "food": "Food", "beverage": "Beverage",
    "lodging": "Lodging", "dj": "DJ", "floral": "Floral", "bakery": "Bakery",
    "stationery": "Stationery", "photography": "Photography",
    "other_ancillary": "Other Ancillary", "service_charge": "Service Charge",
}

# Event-sheet column order.
EVENT_COLUMN_ORDER = ["room_rental", "elopement", "all_inclusive", "food",
                      "beverage", "lodging", "dj", "floral", "bakery",
                      "stationery", "photography", "other_ancillary",
                      "service_charge"]


def event_columns(base):
    """Categories worth a column on this venue's Events sheet.

    Driven by the lines the venue's own P&L carries, so Hadden gets no elopement
    or all-inclusive column and Firefly does.
    """
    present = {ln["key"] for ln in base["lines"]}
    out = []
    for cat in EVENT_COLUMN_ORDER:
        if cat in ANCILLARY_CATEGORIES:
            if "ancillary" in present:
                out.append(cat)
        elif cat in present:
            out.append(cat)
    return out
