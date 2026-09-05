"""Read a monthly actuals workbook from finance and map it onto the model.

The finance file is not a fixed template, so nothing here assumes a layout. The
parser looks for a row of month headers and a column of line labels, matches the
labels against the proforma's own line names (plus an alias table), and returns a
preview for a person to confirm before anything is stored.

Two corrections are detected and proposed rather than applied silently:

  scale  a file kept in whole dollars against a model kept in thousands
  sign   cost lines delivered positive against a model that carries them negative
"""
import difflib
import re
from datetime import datetime

import openpyxl

from . import analysis, store

# Names finance uses that differ from the model's own labels.
ALIASES = {
    "leads": ["leads", "new leads", "inquiries", "inquiry", "enquiries"],
    "tours": ["tours", "tours completed", "site visits", "showings"],
    "contracts": ["contracts", "contracts signed", "bookings", "new bookings",
                  "contracts sold"],
    "events": ["events", "events held", "total events", "weddings and events"],
    "events_oc": ["events original contracts", "oc events", "original contracts",
                  "assumed contracts", "inherited events", "pre close events",
                  "original", "backlog events"],
    "events_new": ["events new contracts", "new events", "new contracts",
                   "new contract events", "new"],
    "room_rental": ["room rental revenue", "venue fee", "venue rental",
                    "rental revenue", "room rental", "venue revenue",
                    "site fee"],
    "food": ["food revenue", "food", "catering revenue", "catering", "f and b food"],
    "beverage": ["beverage revenue", "beverage", "bar revenue", "alcohol revenue",
                 "bar"],
    "lodging": ["lodging revenues", "lodging revenue", "lodging", "accommodation",
                "cabins", "rooms revenue", "overnight"],
    "ancillary": ["ancillary revenue", "ancillary", "add ons", "add on revenue",
                  "vendor revenue", "enhancements"],
    "service_charge": ["service charge", "service fee", "admin fee",
                       "service charges"],
    "cancelled_events": ["cancelled events", "canceled events", "cancellation revenue",
                         "forfeited deposits", "retained deposits"],
    "outside_events": ["outside events", "offsite events", "external events"],
    "discounts": ["discounts", "discount", "concessions", "comps"],
    "other_revenue": ["other revenue", "misc revenue", "miscellaneous revenue",
                      "other income"],
    "total_revenue": ["total revenue", "total sales", "gross revenue", "net revenue",
                      "revenue total"],
    "food_cogs": ["food cogs", "food cost", "cost of food", "catering cogs"],
    "ancillary_cogs": ["ancillary cogs", "ancillary cost", "vendor cost",
                       "cost of ancillary"],
    "alcohol_cogs": ["alcohol cogs", "beverage cogs", "bar cogs", "alcohol cost",
                     "cost of beverage"],
    "other_cogs": ["other cogs", "other cost of sales", "misc cogs"],
    "room_cogs": ["room cogs", "lodging cogs", "lodging cost", "room cost"],
    "total_cogs": ["total cogs", "total cost of goods sold", "cost of goods sold",
                   "total cost of sales"],
    "gross_margin": ["gross margin", "gross profit"],
    "sales_payroll": ["sales team payroll", "sales payroll", "sales wages",
                      "sales salaries"],
    "planning_payroll": ["planning team payroll", "planning payroll",
                         "planning wages", "coordinator payroll", "event planning"],
    "operations_payroll": ["operations team payroll", "operations payroll",
                           "ops payroll", "operations wages", "venue payroll"],
    "ancillary_payroll": ["ancillary payroll", "ancillary wages"],
    "fnb_payroll": ["f and b team payroll", "fnb payroll", "f b payroll",
                    "food and beverage payroll", "kitchen payroll",
                    "banquet payroll"],
    "owner_salaries": ["owner salaries", "owners salary", "owner compensation",
                       "owner draw"],
    "payroll_admin": ["payroll admin and benefit expenses", "payroll taxes",
                      "benefits", "payroll admin", "payroll burden",
                      "taxes and benefits"],
    "other_payroll": ["other payroll", "misc payroll", "contract labor"],
    "total_payroll": ["total payroll", "total labor", "total wages"],
    "marketing": ["marketing expense", "marketing", "advertising", "advertising and marketing"],
    "maintenance": ["maintenance expense", "maintenance", "repairs and maintenance",
                    "r and m", "grounds"],
    "utilities": ["utilities expense", "utilities", "utility"],
    "office": ["office expense", "office", "office supplies", "supplies"],
    "computer": ["computer expense", "computer", "software", "it expense",
                 "technology"],
    "automobile": ["automobile expenses", "automobile", "auto expense", "vehicle",
                   "fuel"],
    "training": ["training and development expense", "training", "development",
                 "training and development"],
    "tax": ["tax expense", "taxes", "property tax", "property taxes"],
    "travel": ["travel expense", "travel", "travel and entertainment"],
    "professional": ["professional expenses", "professional fees", "legal and accounting",
                     "legal", "accounting", "consulting"],
    "rent_expense": ["rent expense", "equipment rent", "equipment rental"],
    "insurance": ["insurance", "insurance expense"],
    "finance": ["finance expenses", "bank fees", "merchant fees", "processing fees",
                "credit card fees", "interest expense"],
    "personal": ["personal expenses", "personal"],
    "other_opex": ["other operating expenses", "other opex", "miscellaneous expense",
                   "other expense", "general and administrative"],
    "total_opex": ["total operating expenses", "total opex", "total expenses",
                   "total operating expense"],
    "ebitdar": ["ebitdar"],
    "rent": ["rent", "base rent", "lease expense", "ground lease"],
    "ebitda": ["ebitda", "net operating income", "noi"],
}

# Lines that must be negative in the stored model.
COST_KEYS = {
    "food_cogs", "ancillary_cogs", "alcohol_cogs", "other_cogs", "room_cogs",
    "total_cogs", "sales_payroll", "planning_payroll", "operations_payroll",
    "ancillary_payroll", "fnb_payroll", "owner_salaries", "payroll_admin",
    "other_payroll", "total_payroll", "marketing", "maintenance", "utilities",
    "office", "computer", "automobile", "training", "tax", "travel",
    "professional", "rent_expense", "insurance", "finance", "personal",
    "other_opex", "total_opex", "rent", "discounts",
}

# Lines that are counts or ratios and must never be rescaled or sign-flipped.
NON_DOLLAR = {"leads", "tours", "contracts", "events", "events_oc", "events_new",
              "lead_to_tour", "tour_to_contract"}

MATCH_THRESHOLD = 0.84
MONTH_NAMES = {m.lower(): i for i, m in enumerate(
    ["", "january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"]) if m}
MONTH_ABBR = {m.lower(): i for i, m in enumerate(analysis.MONTH_ABBR) if m}


def norm(text):
    if text is None:
        return ""
    text = str(text).replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _alias_index(slug):
    idx = {}
    for ln in analysis.line_meta(slug):
        idx.setdefault(norm(ln["label"]), ln["key"])
    for key, names in ALIASES.items():
        for name in names:
            idx.setdefault(norm(name), key)
    return idx


def match_label(raw, idx):
    """Map one spreadsheet label to a model line key, with a confidence."""
    n = norm(raw)
    if not n or len(n) < 2:
        return None, 0.0
    if n in idx:
        return idx[n], 1.0
    best = difflib.get_close_matches(n, list(idx), n=1, cutoff=MATCH_THRESHOLD)
    if best:
        return idx[best[0]], round(difflib.SequenceMatcher(None, n, best[0]).ratio(), 3)
    return None, 0.0


def parse_period(value):
    """Turn a header cell into YYYY-MM, or None if it is not a month."""
    if isinstance(value, datetime):
        return f"{value.year:04d}-{value.month:02d}"
    if isinstance(value, (int, float)):
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    m = re.match(r"^(\d{4})[-/](\d{1,2})$", text)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{1,2})[-/](\d{4})$", text)
    if m:
        return f"{int(m.group(2)):04d}-{int(m.group(1)):02d}"
    m = re.match(r"^([A-Za-z]{3,9})[\s\-']+(\d{2,4})$", text)
    if m:
        name = m.group(1).lower()
        month = MONTH_NAMES.get(name) or MONTH_ABBR.get(name[:3])
        if month:
            year = int(m.group(2))
            year += 2000 if year < 100 else 0
            return f"{year:04d}-{month:02d}"
    return None


def _find_header(ws, max_scan=40):
    """Best (row, {col: ym}) pair of month headers on a sheet."""
    best = (None, {})
    for r in range(1, min(ws.max_row, max_scan) + 1):
        found = {}
        for c in range(1, ws.max_column + 1):
            ym = parse_period(ws.cell(r, c).value)
            if ym:
                found[c] = ym
        if len(found) > len(best[1]):
            best = (r, found)
    return best


def _find_label_col(ws, header_row, idx, max_col=8):
    """Column of line labels: the one matching the most known model lines."""
    best, best_hits = 1, -1
    for c in range(1, min(ws.max_column, max_col) + 1):
        hits = 0
        for r in range(header_row + 1, ws.max_row + 1):
            key, _ = match_label(ws.cell(r, c).value, idx)
            if key:
                hits += 1
        if hits > best_hits:
            best, best_hits = c, hits
    return best, best_hits


def preview(path, slug, sheet=None):
    """Parse a workbook and describe what would be imported. Stores nothing."""
    wb = openpyxl.load_workbook(path, data_only=True)
    idx = _alias_index(slug)

    candidates = []
    for ws in wb.worksheets:
        row, cols = _find_header(ws)
        if not cols:
            continue
        label_col, hits = _find_label_col(ws, row, idx)
        candidates.append((hits, len(cols), ws.title, row, cols, label_col))
    if not candidates:
        return {"ok": False,
                "error": "No month headers found. The file needs a row of month "
                         "columns (e.g. Sep-26, Oct-26) and a column of line names."}

    if sheet:
        chosen = next((c for c in candidates if c[2] == sheet), None)
        if chosen is None:
            return {"ok": False, "error": f"Sheet '{sheet}' has no month headers."}
    else:
        chosen = max(candidates, key=lambda c: (c[0], c[1]))
    hits, _, title, header_row, month_cols, label_col = chosen
    ws = wb[title]

    base_months = {m["ym"]: m for m in store.baseline(slug)["months"]}
    in_model = {c: ym for c, ym in month_cols.items() if ym in base_months}

    rows, unmatched = [], []
    seen = set()
    for r in range(header_row + 1, ws.max_row + 1):
        raw = ws.cell(r, label_col).value
        if raw is None or not str(raw).strip():
            continue
        key, conf = match_label(raw, idx)
        values = {}
        for c, ym in in_model.items():
            v = ws.cell(r, c).value
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                values[ym] = float(v)
        if not key:
            if values:
                unmatched.append({"row": r, "raw": str(raw).strip()})
            continue
        if key in seen or not values:
            continue
        seen.add(key)
        rows.append({"row": r, "raw": str(raw).strip(), "key": key,
                     "label": next((ln["label"] for ln in analysis.line_meta(slug)
                                    if ln["key"] == key), key),
                     "confidence": conf, "by_month": values})

    scale = _suggest_scale(rows, base_months)
    flip = _suggest_flip(rows)
    return {
        "ok": True,
        "sheet": title,
        "sheets": [c[2] for c in candidates],
        "header_row": header_row,
        "label_col": label_col,
        "months": sorted(set(in_model.values())),
        "months_skipped": sorted({ym for ym in month_cols.values()
                                  if ym not in base_months}),
        "rows": rows,
        "unmatched": unmatched[:25],
        "suggest_scale": scale,
        "suggest_flip_costs": flip,
        "matched": len(rows),
    }


def _suggest_scale(rows, base_months):
    """1 if the file is already in thousands, 0.001 if it is in whole dollars."""
    ratios = []
    for row in rows:
        if row["key"] not in ("total_revenue", "room_rental", "total_payroll"):
            continue
        for ym, v in row["by_month"].items():
            plan = base_months.get(ym, {}).get("lines", {}).get(row["key"])
            if plan and abs(plan) > 1 and v:
                ratios.append(abs(v) / abs(plan))
    if not ratios:
        return 1.0
    ratios.sort()
    median = ratios[len(ratios) // 2]
    return 0.001 if median > 100 else 1.0


def _suggest_flip(rows):
    """True when cost lines arrive positive and need negating."""
    pos = neg = 0
    for row in rows:
        if row["key"] not in COST_KEYS:
            continue
        for v in row["by_month"].values():
            if v > 0:
                pos += 1
            elif v < 0:
                neg += 1
    return pos > neg and pos > 0


def apply_preview(slug, prev, include_keys, months, scale=1.0, flip_costs=False,
                  filename=None):
    """Commit a confirmed preview into the actuals store, month by month."""
    include = set(include_keys)
    by_month = {}
    for row in prev["rows"]:
        if row["key"] not in include:
            continue
        for ym, v in row["by_month"].items():
            if ym not in months:
                continue
            value = v
            if row["key"] not in NON_DOLLAR:
                value *= scale
                if flip_costs and row["key"] in COST_KEYS and value > 0:
                    value = -value
            by_month.setdefault(ym, {})[row["key"]] = round(value, 6)

    written = []
    for ym in sorted(by_month):
        store.record(slug, ym, by_month[ym], "upload", note=filename)
        written.append(ym)
    return written
