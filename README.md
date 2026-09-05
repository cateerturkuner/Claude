# Post-Close Analysis

Tracks how an acquired venue actually performs against the pro forma we
underwrote before closing — monthly, and cumulatively across each post-close
year — and uses the accumulated variance to say where the pro forma model
itself is wrong.

Served at `/PostCloseAnalysis` inside the existing Walters Hospitality Flask app.

## The two questions it answers

1. **How is this venue doing?** Month-by-month and year-to-date actual vs pro
   forma across the whole funnel (leads → tours → contracts → events) and the
   whole P&L, plus attachment rates and $ per ancillary.
2. **What should we change in the next pro forma?** Which lines miss in the
   same direction month after month, whether a revenue gap is volume or rate,
   whether attachment programmes landed on schedule, and — once more than one
   venue is loaded — which assumptions miss at *every* venue rather than one.

## Periods

"Year" always means a **post-close year**, never a calendar year. Y1 is the
twelve months beginning the close month. The month → year mapping is read from
row 3 of the source workbook's Detailed P&L tab rather than recomputed, so it
matches the model exactly.

For Hadden Estate (closed September 2026):

| Year | Months |
|------|--------|
| Y1 | Sep 2026 – Aug 2027 |
| Y2 | Sep 2027 – Aug 2028 |
| Y3 | Sep 2028 – Aug 2029 |
| Y4 | Sep 2029 – Dec 2029 (model stub) |

## Accrual basis

Revenue and its associated costs are recognised on the **date the event
occurs**. The stages above events are counted in the month the thing happened,
not the month the event lands:

- **Leads** — enquiries received that month
- **Tours** — tours that took place that month
- **Contracts** — contracts signed that month, whenever the event falls
- **Events** — events held that month; this is where money is recognised

So the four stages describe different deals. Conversion rates are same-month
ratios, a pace measure rather than a cohort measure — which is exactly how the
pro forma computes them.

## Sign convention

Every cost line is carried negative. That makes `actual − plan` favourable when
positive on *every* line, expenses included, so nothing in the UI needs a
per-line sign flip and a green number always means good news.

## Layout

```
postclose/
  __init__.py       register(app) mounts the blueprint
  routes.py         views, JSON API, Jinja number filters
  analysis.py       variance, post-close year roll-ups, attachment attribution
  signals.py        persistence, materiality, bridges, cross-venue consensus
  ingest.py         parses a finance workbook onto the model's line names
  store.py          baseline (read-only) and actuals (read-write) JSON
  data/
    baseline_<slug>.json   locked pro forma — never written by the app
    actuals_<slug>.json    everything reported since close
  templates/postclose/
tools/
  extract_baseline.py        workbook -> baseline JSON
  deploy_pythonanywhere.py   push files + reload the web app
```

## Adding a venue

```bash
python3 tools/extract_baseline.py path/to/Venue_Monthly_Forecast.xlsx venue_slug 2027-03
```

The third argument is the close month (`YYYY-MM`); omit it to start at the first
forecast column the workbook tags with a post-close year. The venue appears in
the picker on the next request. The workbook needs a `Detailed P&L` tab laid out
like Hadden's (row 3 post-close year tags, row 9 month-end dates, line names in
column C) and a `Revenue Analysis` tab with the Y1/Y2/Y3 driver columns.

## Loading a month of actuals

**From a finance workbook.** Data tab → upload. No fixed template: the parser
finds a row of month headers (`Sep-26`, `2026-09`, a real date) and a column of
line names, matches those names against the venue's own P&L labels plus an alias
table, and shows the mapping for confirmation before saving anything. It detects
and offers to fix two common mismatches — a file kept in whole dollars against a
model kept in thousands, and cost lines delivered positive. Months outside the
pro forma window are ignored.

**By hand.** Same tab, lower panel. Typed values are marked `manual` and win
over an uploaded file. Blank leaves an existing value alone.

Subtotals (Gross Margin, EBITDA, Total Payroll…) are derived from their
components when the source does not report them. A reported subtotal always
wins — recomputing over the top would hide a mapping mistake rather than expose
it.

Attachment detail (events that bought each category, and the revenue they
produced, split original vs new contract) is optional but is the only way to
tell "we sold it to fewer couples" apart from "we charged less".

## Attachment attribution

A category's revenue gap splits three ways, and the three add exactly to the
total:

| Effect | Holds constant | Answers |
|--------|----------------|---------|
| **Events** | attachment and price at plan | did fewer events happen? |
| **Attach** | price at plan | did a different share of events buy it? |
| **Price** | nothing | did the ones who bought pay differently? |

"We haven't stood the catering kitchen up yet" shows in Attach. "We priced
floral wrong" shows in Price. Where the pro forma carried a category at nil the
cascade would hand everything to Price, so those rows are reported wholly as
attachment and flagged `nil in PF`.

## Materiality

Findings are ranked by absolute dollar gap, not percentage, so a 12% miss on
room rental outranks a 90% miss on office supplies. A dollar gap under 0.5% of
plan revenue is classed `immaterial` however large its percentage. A line is
called **structural** — a modelling error rather than an incident — only when it
has missed in the same direction for three or more consecutive months by at
least 10%.

## Deploying

```bash
export PA_USERNAME=... PA_TOKEN=...
python3 tools/deploy_pythonanywhere.py --dry-run   # inspect the manifest
python3 tools/deploy_pythonanywhere.py
```

Reported actuals on the server are never overwritten — `actuals_*.json` is
excluded from the manifest, so a deploy cannot destroy months already entered.

Mounting into the host app takes two lines:

```python
from postclose import register
register(app)          # claims /PostCloseAnalysis and nothing else
```

The blueprint needs `app.secret_key` set (upload previews are held in the
session) and inherits whatever `before_request` authentication the host app
already applies.

## Running it standalone

```bash
pip install -r requirements.txt
python3 app_dev.py      # http://127.0.0.1:5001/PostCloseAnalysis
```
