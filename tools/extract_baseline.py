"""Extract a post-close proforma baseline from a venue forecast workbook.

    python3 tools/extract_baseline.py <workbook.xlsx> <venue-slug> [close YYYY-MM]

Reads the P&L tab by label rather than by row number, so venues with different
line sets extract without a code change. Segments -- separate event venues or
product lines sharing one cost base, like Firefly's Barn and Chapel -- are
detected from the label pattern and given their own funnel, events and
attachment drivers while expenses stay at venue level.
"""
import json
import re
import sys
from datetime import datetime

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter

sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from postclose import lines as L  # noqa: E402

LABEL_COL = 3          # column C in every model so far
YEAR_TAG_ROW = 3       # post-close year index, 1-based, on forecast columns
DATE_ROW = 9           # month-end dates
MAX_BLANK_RUN = 4      # forecast blocks contain spacer columns between years

# "Original - Barn" / "New - Chapel" / "Events - Barn"; and "Barn Contracts".
SEG_EVENT_RE = re.compile(r"^(original|new|events)\s*[-–]\s*(.+)$", re.I)
SEG_CONTRACT_RE = re.compile(r"^(.+?)\s+contracts$", re.I)
SEG_ROLE = {"original": "events_oc", "new": "events_new", "events": "events"}
# "% of Annual Contracts" is a seasonality row, not a segment called "% of Annual".
NOT_A_SEGMENT = re.compile(r"^\s*%|annual|total\b", re.I)

# Revenue Analysis rows. Identical across every model built so far.
RA_CATEGORIES = [
    ("room_rental", "Room Rental", 29, 43, 60, 75),
    ("food", "Food", 30, 44, 61, 76),
    ("beverage", "Beverage", 31, 45, 62, 77),
    ("lodging", "Lodging", 32, 46, 63, 78),
    ("dj", "DJ", 33, 47, 64, 79),
    ("floral", "Floral", 34, 48, 65, 80),
    ("bakery", "Bakery", 35, 49, 66, 81),
    ("stationery", "Stationery", 36, 50, 67, 82),
    ("photography", "Photography", 37, 51, 68, 83),
    ("other_ancillary", "Other Ancillary", 38, 52, 69, 84),
]
RA_SERVICE_CHARGE_ROW = 85
RA_YEAR_COLS = {1: "G", 2: "H", 3: "I"}
RA_DRIVER_COLS = {1: "K", 2: "L", 3: "M"}
RA_COMMENT_COL = "T"
RA_BENCH_COLS = {"venue": "P", "region": "Q", "wh_avg": "R"}
RA_ROWS = {"events_oc": 11, "events_new": 12, "events_total": 13,
           "revenue_oc": 16, "revenue_oc_new": 17, "revenue_new": 18,
           "revenue_total": 19, "rev_per_event_oc": 22,
           "rev_per_event_oc_new": 23, "rev_per_event_new": 24,
           "rev_per_event_total": 25}


def num(v):
    if isinstance(v, bool) or v is None:
        return None
    return round(float(v), 6) if isinstance(v, (int, float)) else None


def cell(ws, row, col_letter):
    return num(ws[f"{col_letter}{row}"].value)


def slug_of(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).strip().lower()).strip("_")


def find_pl_sheet(wb):
    """The P&L tab: the one carrying post-close year tags on row 3."""
    for ws in wb.worksheets:
        if ws.max_column < 20:
            continue
        for c in range(1, min(ws.max_column, 120) + 1):
            if isinstance(ws.cell(YEAR_TAG_ROW, c).value, (int, float)) and \
               isinstance(ws.cell(DATE_ROW, c).value, datetime):
                return ws
    raise SystemExit("No sheet has post-close year tags on row 3.")


def forecast_columns(ws, close_ym=None):
    """Forecast month columns, tolerating the spacer columns between years."""
    cols = []
    first = None
    for c in range(1, ws.max_column + 1):
        if isinstance(ws.cell(YEAR_TAG_ROW, c).value, (int, float)) and \
           isinstance(ws.cell(DATE_ROW, c).value, datetime):
            first = c
            break
    if first is None:
        raise SystemExit("Could not locate the start of the forecast block.")

    if close_ym:
        want = datetime.strptime(close_ym, "%Y-%m")
        for c in range(first, ws.max_column + 1):
            d = ws.cell(DATE_ROW, c).value
            if isinstance(d, datetime) and (d.year, d.month) == (want.year, want.month):
                first = c
                break

    blanks = 0
    for c in range(first, ws.max_column + 1):
        d, tag = ws.cell(DATE_ROW, c).value, ws.cell(YEAR_TAG_ROW, c).value
        if isinstance(d, datetime) and isinstance(tag, (int, float)):
            cols.append((c, d, int(tag)))
            blanks = 0
            continue
        blanks += 1
        if blanks > MAX_BLANK_RUN:
            break
    return cols


def read_labels(ws):
    """Every label in the label column, with its row, in sheet order."""
    out = []
    for r in range(1, ws.max_row + 1):
        raw = ws.cell(r, LABEL_COL).value
        if isinstance(raw, str) and raw.strip():
            out.append((r, raw.strip()))
    return out


def _add_segment(segments, name, role, row):
    """Collect a segment row, merging singular and plural spellings.

    A model may say "Elopement Contracts" in one place and "Original -
    Elopements" in another. Those are one segment, so the key drops a trailing
    plural and the fuller spelling is kept as the label.
    """
    key = re.sub(r"s$", "", slug_of(name))
    seg = segments.setdefault(key, {"label": name, "rows": {}})
    if len(name) > len(seg["label"]):
        seg["label"] = name
    seg["rows"].setdefault(role, row)


def build_line_map(ws, labelled):
    """Match labels to canonical keys, and pick up segment rows separately.

    The first matching row wins. Models repeat some labels below the P&L in memo
    or seasonality blocks, and those must not overwrite the real line.
    """
    line_rows, segments, unmatched = {}, {}, []
    for row, raw in labelled:
        norm = L.normalise(raw)
        if norm in L.SECTION_HEADERS:
            continue

        m = SEG_EVENT_RE.match(raw)
        if m and not NOT_A_SEGMENT.match(m.group(2)):
            _add_segment(segments, m.group(2).strip(),
                         SEG_ROLE[m.group(1).lower()], row)
            continue

        m = SEG_CONTRACT_RE.match(raw)
        if m and not NOT_A_SEGMENT.match(m.group(1)):
            _add_segment(segments, m.group(1).strip(), "contracts", row)
            continue

        key = L.LABEL_INDEX.get(norm)
        if key:
            line_rows.setdefault(key, row)
        else:
            unmatched.append((row, raw))

    bare = {re.sub(r"s$", "", slug_of(raw)): (row, raw) for row, raw in unmatched}
    for key, seg in segments.items():
        if "events" not in seg["rows"] and key in bare:
            seg["rows"]["events"] = bare[key][0]
            unmatched = [u for u in unmatched if u[0] != bare[key][0]]
    return line_rows, segments, unmatched


def series(ws, row, cols):
    return [num(ws.cell(row, c).value) for c, _, _ in cols]


def drop_rollup_segments(segments, ws, cols):
    """Remove segments that are just the sum of others, like Firefly's 'B&C'.

    The workbook carries a combined Barn-and-Chapel line for convenience. Kept as
    a segment it would double-count every event, so it is identified structurally
    -- its monthly event series equals the sum of two or more others -- rather
    than by name.
    """
    totals = {}
    for key, seg in segments.items():
        row = seg["rows"].get("events") or seg["rows"].get("contracts")
        totals[key] = [v or 0 for v in series(ws, row, cols)] if row else None

    rollups = set()
    keys = [k for k, v in totals.items() if v]
    for key in keys:
        others = [k for k in keys if k != key and k not in rollups]
        for size in (len(others), 2):
            if size < 2 or size > len(others):
                continue
            import itertools
            for combo in itertools.combinations(others, size):
                summed = [sum(totals[k][i] for k in combo)
                          for i in range(len(totals[key]))]
                if summed == totals[key] and any(summed):
                    rollups.add(key)
                    break
            if key in rollups:
                break
    for key in rollups:
        segments[key]["rollup_of"] = True
    return {k: v for k, v in segments.items() if k not in rollups}, rollups


# ------------------------------------------------------------ revenue analysis
def ra_sheet_for(wb, seg_label):
    """The Revenue Analysis tab belonging to a segment, if it has one."""
    want = L.normalise(seg_label).rstrip("s")
    best = None
    for ws in wb.worksheets:
        title = L.normalise(ws.title)
        if not title.startswith("revenue analysis"):
            continue
        suffix = title.replace("revenue analysis", "").strip(" -–")
        if suffix.rstrip("s") == want:
            return ws
        if suffix in ("", "total"):
            best = best or ws
    return best if not want else None


def extract_drivers(ra):
    """Annual attachment rates and $/event from one Revenue Analysis tab."""
    drivers = {"years": {}, "categories": []}
    for year, gcol in RA_YEAR_COLS.items():
        drivers["years"][str(year)] = {
            name: cell(ra, row, gcol) for name, row in RA_ROWS.items()
        }
    for key, label, oc_att, nc_att, oc_rev, nc_rev in RA_CATEGORIES:
        entry = {
            "key": key, "label": label,
            "comment": (ra[f"{RA_COMMENT_COL}{nc_att}"].value
                        or ra[f"{RA_COMMENT_COL}{nc_rev}"].value or None),
            "benchmark": {n: cell(ra, nc_rev, c) for n, c in RA_BENCH_COLS.items()},
            "oc": {"attach_rate": {}, "attach_events": {}, "revenue": {},
                   "rev_per_event": {}},
            "new": {"attach_rate": {}, "attach_events": {}, "revenue": {},
                    "rev_per_event": {}},
        }
        for year in (1, 2, 3):
            y, g, d = str(year), RA_YEAR_COLS[year], RA_DRIVER_COLS[year]
            entry["oc"]["attach_rate"][y] = cell(ra, oc_att, d)
            entry["oc"]["attach_events"][y] = cell(ra, oc_att, g)
            entry["oc"]["revenue"][y] = cell(ra, oc_rev, g)
            entry["oc"]["rev_per_event"][y] = cell(ra, oc_rev, d)
            entry["new"]["attach_rate"][y] = cell(ra, nc_att, d)
            entry["new"]["attach_events"][y] = cell(ra, nc_att, g)
            entry["new"]["revenue"][y] = cell(ra, nc_rev, g)
            entry["new"]["rev_per_event"][y] = cell(ra, nc_rev, d)
        drivers["categories"].append(entry)
    drivers["service_charge"] = {
        "label": "Service Charge",
        "comment": ra[f"{RA_COMMENT_COL}{RA_SERVICE_CHARGE_ROW}"].value,
        "new": {
            "rate": {str(y): cell(ra, RA_SERVICE_CHARGE_ROW, RA_DRIVER_COLS[y])
                     for y in (1, 2, 3)},
            "revenue": {str(y): cell(ra, RA_SERVICE_CHARGE_ROW, RA_YEAR_COLS[y])
                        for y in (1, 2, 3)},
        },
    }
    return drivers


# ---------------------------------------------------------------------- build
def extract(path, slug, close_ym=None):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = find_pl_sheet(wb)
    venue_name = ws.cell(5, LABEL_COL).value or slug

    cols = forecast_columns(ws, close_ym)
    labelled = read_labels(ws)
    line_rows, segments, unmatched = build_line_map(ws, labelled)
    segments, rollups = drop_rollup_segments(segments, ws, cols)

    ordered = [k for k in L.ORDER if k in line_rows]
    lines_meta = [{**L.BY_KEY[k], "source_row": line_rows[k]} for k in ordered]

    months = []
    for i, (c, d, tag) in enumerate(cols):
        month = {
            "ym": f"{d.year:04d}-{d.month:02d}",
            "date": d.strftime("%Y-%m-%d"),
            "post_close_year": tag,
            "lines": {k: num(ws.cell(line_rows[k], c).value) for k in ordered},
            "segments": {},
        }
        for key, seg in segments.items():
            month["segments"][key] = {
                role: num(ws.cell(row, c).value)
                for role, row in seg["rows"].items()
            }
        months.append(month)

    # A venue with no segment rows still gets one segment, mirroring its own
    # event and contract lines. Everything downstream then iterates segments
    # uniformly, and a single-segment venue simply shows no segment selector.
    if not segments:
        implicit = {role: line_rows[role]
                    for role in ("contracts", "events_oc", "events_new", "events")
                    if role in line_rows}
        if implicit:
            segments = {slug: {"label": venue_name, "rows": implicit,
                               "implicit": True}}
            for month, (c, _, _) in zip(months, cols):
                month["segments"][slug] = {
                    role: num(ws.cell(row, c).value)
                    for role, row in implicit.items()}

    # The model's own total tab, used for venue-level drivers and as the
    # implicit segment's own drivers when a venue has no segment split.
    total_ra = next((w for w in wb.worksheets
                     if L.normalise(w.title) in ("revenue analysis",
                                                 "revenue analysis - total")), None)

    seg_out = []
    for key, seg in segments.items():
        ra = total_ra if seg.get("implicit") else ra_sheet_for(wb, seg["label"])
        seg_out.append({
            "key": key, "label": seg["label"],
            "roles": sorted(seg["rows"]),
            "implicit": seg.get("implicit", False),
            "ra_sheet": ra.title if ra else None,
            "drivers": extract_drivers(ra) if ra else None,
        })
    seg_out.sort(key=lambda s: (s["drivers"] is None, s["label"]))

    drivers = extract_drivers(total_ra) if total_ra else (
        seg_out[0]["drivers"] if len(seg_out) == 1 else None)

    profit_key = next((k for k in L.PROFIT_PREFERENCE if k in line_rows), None)

    return {
        "slug": slug,
        "venue": venue_name,
        "units": "thousands",
        "source_file": path.split("/")[-1],
        "source_sheet": ws.title,
        "extracted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "close_month": months[0]["ym"] if months else None,
        "profit_key": profit_key,
        "lines": lines_meta,
        "months": months,
        "segments": seg_out,
        "rollups_ignored": sorted(rollups),
        "drivers": drivers,
        "unmatched_labels": [{"row": r, "label": t} for r, t in unmatched][:40],
    }


if __name__ == "__main__":
    src, slug = sys.argv[1], sys.argv[2]
    close = sys.argv[3] if len(sys.argv) > 3 else None
    data = extract(src, slug, close)
    with open(f"postclose/data/baseline_{slug}.json", "w") as fh:
        json.dump(data, fh, indent=1)

    per_year = {}
    for m in data["months"]:
        per_year[m["post_close_year"]] = per_year.get(m["post_close_year"], 0) + 1
    print(f"baseline_{slug}.json")
    print(f"  sheet        {data['source_sheet']}")
    print(f"  close        {data['close_month']}  months/year {per_year}")
    print(f"  lines        {len(data['lines'])}  profit line: {data['profit_key']}")
    seg_names = [s["label"] + ("" if s["drivers"] else " (no attachment)")
                 for s in data["segments"]]
    print(f"  segments     {seg_names or 'none'}")
    if data["rollups_ignored"]:
        print(f"  rollups      ignored as double-counting: {data['rollups_ignored']}")
    if data["unmatched_labels"]:
        print(f"  unmatched    {[u['label'] for u in data['unmatched_labels']][:12]}")
