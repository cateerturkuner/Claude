"""Variance analysis: reported actuals against the locked proforma.

Sign convention. Every cost line in the source model is carried as a negative
number, so `actual - plan` is favourable when positive for *every* line in the
P&L, funnel and conversion set alike. Nothing needs a per-line sign flip.

Periods. "Year" always means a post-close year (Y1 = the twelve months from the
close month), never a calendar year. The month -> year mapping is taken from the
baseline workbook itself rather than recomputed.
"""
from datetime import date

from . import store

MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

GROUP_LABELS = {
    "funnel": "Sales Funnel",
    "revenue": "Revenue",
    "cogs": "Cost of Goods Sold",
    "payroll": "Payroll",
    "opex": "Operating Expenses",
    "total": "Totals",
}

# Lines that are rates/ratios and must be re-derived rather than summed when
# rolling months up into a year.
DERIVED = {
    "lead_to_tour": ("tours", "leads"),
    "tour_to_contract": ("contracts", "tours"),
}

REVENUE_KEYS = ["room_rental", "food", "beverage", "lodging", "ancillary",
                "service_charge", "cancelled_events", "outside_events",
                "discounts", "other_revenue"]
COGS_KEYS = ["food_cogs", "ancillary_cogs", "alcohol_cogs", "other_cogs",
             "room_cogs"]
PAYROLL_KEYS = ["sales_payroll", "planning_payroll", "operations_payroll",
                "ancillary_payroll", "fnb_payroll", "owner_salaries",
                "payroll_admin", "other_payroll"]
OPEX_KEYS = ["marketing", "maintenance", "utilities", "office", "computer",
             "automobile", "training", "tax", "travel", "professional",
             "rent_expense", "insurance", "finance", "personal", "other_opex"]


# Subtotals derived from their components when finance does not report them.
# A reported subtotal always wins -- finance's own total is authoritative, and
# silently recomputing it would hide a mapping mistake rather than expose it.
SUBTOTALS = [
    ("events", lambda g: _sum([g("events_oc"), g("events_new")])),
    ("total_revenue", lambda g: _sum(g(k) for k in REVENUE_KEYS)),
    ("total_cogs", lambda g: _sum(g(k) for k in COGS_KEYS)),
    ("gross_margin", lambda g: _sum([g("total_revenue"), g("total_cogs")])),
    ("total_payroll", lambda g: _sum(g(k) for k in PAYROLL_KEYS)),
    ("total_opex", lambda g: _sum(g(k) for k in OPEX_KEYS)),
    ("ebitdar", lambda g: _sum([g("gross_margin"), g("total_payroll"),
                                g("total_opex")])),
    ("ebitda", lambda g: _sum([g("ebitdar"), g("rent")])),
]

# Headline metrics surfaced as tiles, in display order.
HEADLINES = [
    ("total_revenue", "Total Revenue", "usd"),
    ("ebitda", "EBITDA", "usd"),
    ("events", "Events", "count"),
    ("rev_per_event", "Revenue / Event", "usd"),
    ("contracts", "Contracts", "count"),
    ("leads", "Leads", "count"),
]


def ym_label(ym):
    y, m = ym.split("-")
    return f"{MONTH_ABBR[int(m)]} {y[2:]}"


def _safe_div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def _sum(values):
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def fill_subtotals(bucket, derived_keys=None):
    """Compute any subtotal the source did not supply, from its components.

    Finance packages routinely omit Gross Margin or EBITDA, or stop at Total
    Revenue. Without this, those rows read as "not reported" even though every
    component arrived. Subtotals are filled in dependency order so EBITDA can be
    built on a Gross Margin that was itself just derived.
    """
    derived = derived_keys if derived_keys is not None else set()

    def get(key):
        return bucket.get(key)

    for key, rule in SUBTOTALS:
        if bucket.get(key) is not None:
            continue
        value = rule(get)
        if value is not None:
            bucket[key] = value
            derived.add(key)
    return bucket


def add_derived(bucket):
    """Attach ratio metrics that are computed from other lines, not summed."""
    bucket["rev_per_event"] = _safe_div(bucket.get("total_revenue"),
                                        bucket.get("events"))
    bucket["ebitda_margin"] = _safe_div(bucket.get("ebitda"),
                                        bucket.get("total_revenue"))
    bucket["gm_margin"] = _safe_div(bucket.get("gross_margin"),
                                    bucket.get("total_revenue"))
    bucket["lead_to_contract"] = _safe_div(bucket.get("contracts"),
                                           bucket.get("leads"))
    for key, (num_key, den_key) in DERIVED.items():
        bucket[key] = _safe_div(bucket.get(num_key), bucket.get(den_key))
    return bucket


def variance(actual, plan):
    """Signed variance and percent-of-plan. Positive is always favourable."""
    if actual is None or plan is None:
        return {"var": None, "pct": None}
    var = actual - plan
    pct = (var / abs(plan)) if plan else None
    return {"var": var, "pct": pct}


def line_meta(slug):
    return store.baseline(slug)["lines"]


def _plan_by_month(slug):
    return {m["ym"]: m for m in store.baseline(slug)["months"]}


def years_available(slug):
    return sorted({m["post_close_year"] for m in store.baseline(slug)["months"]})


def current_year(slug):
    """The post-close year the venue is in today, clamped to the model range."""
    plan = store.baseline(slug)["months"]
    today = date.today().strftime("%Y-%m")
    for m in plan:
        if m["ym"] >= today:
            return m["post_close_year"]
    return plan[-1]["post_close_year"] if plan else 1


def reported_months(slug, year):
    """Months of `year` that have actuals, without building the full view."""
    act = store.actuals(slug)
    return sorted(m["ym"] for m in store.baseline(slug)["months"]
                  if m["post_close_year"] == year
                  and act["months"].get(m["ym"], {}).get("lines"))


def has_attachment(slug, year):
    act = store.actuals(slug)
    return any(act["months"].get(ym, {}).get("ancillary")
               for ym in reported_months(slug, year))


def build(slug, year):
    """Everything the month / YTD / full-year views need for one post-close year."""
    base = store.baseline(slug)
    act = store.actuals(slug)
    keys = [ln["key"] for ln in base["lines"]]

    months = []
    for m in base["months"]:
        if m["post_close_year"] != year:
            continue
        reported = act["months"].get(m["ym"], {})
        plan = add_derived({k: m["lines"].get(k) for k in keys})
        actual_lines = reported.get("lines", {})
        has_actual = bool(actual_lines)
        derived_keys = set()
        actual = {}
        if has_actual:
            actual = add_derived(
                fill_subtotals({k: actual_lines.get(k) for k in keys}, derived_keys))
        months.append({
            "ym": m["ym"],
            "label": ym_label(m["ym"]),
            "date": m["date"],
            "plan": plan,
            "actual": actual,
            "var": {k: variance(actual.get(k), plan.get(k)) for k in plan},
            "has_actual": has_actual,
            "source": reported.get("source"),
            "updated_at": reported.get("updated_at"),
            "field_source": reported.get("field_source", {}),
            "derived_keys": sorted(derived_keys),
            "n_reported_lines": len(actual_lines),
            "note": reported.get("note"),
        })

    closed = [m for m in months if m["has_actual"]]
    open_months = [m for m in months if not m["has_actual"]]

    # Year to date: plan restated over exactly the months that have reported.
    ytd_plan = add_derived({k: _sum(m["plan"].get(k) for m in closed) for k in keys})
    ytd_actual = add_derived({k: _sum(m["actual"].get(k) for m in closed) for k in keys})

    # Full year: plan for all twelve, and a projection that keeps reported months
    # and falls back to plan for months not yet closed.
    fy_plan = add_derived({k: _sum(m["plan"].get(k) for m in months) for k in keys})
    fy_proj = add_derived({
        k: _sum([m["actual"].get(k) for m in closed] + [m["plan"].get(k) for m in open_months])
        for k in keys
    })

    all_keys = list(fy_plan.keys())
    return {
        "slug": slug,
        "venue": base["venue"],
        "year": year,
        "years": years_available(slug),
        "close_month": base["close_month"],
        "lines": base["lines"],
        "months": months,
        "reported_months": [m["ym"] for m in closed],
        "n_reported": len(closed),
        "n_months": len(months),
        "ytd": {
            "plan": ytd_plan, "actual": ytd_actual,
            "var": {k: variance(ytd_actual.get(k), ytd_plan.get(k)) for k in all_keys},
        },
        "fy": {
            "plan": fy_plan, "projected": fy_proj,
            "var": {k: variance(fy_proj.get(k), fy_plan.get(k)) for k in all_keys},
        },
    }


# ------------------------------------------------------------------ ancillary
def ancillary(slug, year):
    """Attachment rate and $/attached-event, proforma vs reported.

    The proforma states these annually, so reported figures are rolled to a
    year-to-date rate and compared against the annual assumption. Where only
    revenue was reported, attachment is left blank rather than guessed.
    """
    base = store.baseline(slug)
    act = store.actuals(slug)
    view = build(slug, year)
    y = str(year)

    reported = [ym for ym in view["reported_months"]]
    events_actual = {"oc": 0.0, "new": 0.0}
    for ym in reported:
        lines = act["months"].get(ym, {}).get("lines", {})
        events_actual["oc"] += lines.get("events_oc") or 0
        events_actual["new"] += lines.get("events_new") or 0

    # Proforma events for the same slice of months, so rates compare like for like.
    plan_by_ym = _plan_by_month(slug)
    events_plan = {"oc": 0.0, "new": 0.0}
    for ym in reported:
        pl = plan_by_ym.get(ym, {}).get("lines", {})
        events_plan["oc"] += pl.get("events_oc") or 0
        events_plan["new"] += pl.get("events_new") or 0

    rows = []
    for cat in base["drivers"]["categories"]:
        rep = {}
        for ym in reported:
            entry = act["months"].get(ym, {}).get("ancillary", {}).get(cat["key"], {})
            for k, v in entry.items():
                if isinstance(v, (int, float)):
                    rep[k] = rep.get(k, 0.0) + v
        row = {"key": cat["key"], "label": cat["label"], "comment": cat["comment"],
               "benchmark": cat["benchmark"], "cohorts": {}}
        for cohort in ("oc", "new"):
            plan_rate = cat[cohort]["attach_rate"].get(y)
            plan_dollar = cat[cohort]["rev_per_event"].get(y)
            att_events = rep.get(f"{cohort}_events")
            rev = rep.get(f"{cohort}_rev")
            act_rate = _safe_div(att_events, events_actual[cohort] or None)
            act_dollar = _safe_div(rev, att_events)
            # Nothing attached is a real, reportable outcome, not missing data:
            # the shortfall is entirely an attachment effect, and there is no
            # price to observe. Hold price at plan so it contributes zero.
            if att_events == 0 and rev in (0, None):
                act_rate, act_dollar = 0.0, plan_dollar
            row["cohorts"][cohort] = {
                "plan_rate": plan_rate, "actual_rate": act_rate,
                "rate_var": variance(act_rate, plan_rate),
                "plan_dollar": plan_dollar, "actual_dollar": act_dollar,
                "dollar_var": variance(act_dollar, plan_dollar),
                "plan_year_revenue": cat[cohort]["revenue"].get(y),
                "actual_revenue": rev,
                "attached_events": att_events,
                "decomposition": decompose(
                    events_plan[cohort], events_actual[cohort],
                    plan_rate, act_rate, plan_dollar, act_dollar),
            }
        rows.append(row)

    return {
        "rows": rows,
        "events_plan": events_plan,
        "events_actual": events_actual,
        "reported_months": reported,
        "service_charge": base["drivers"]["service_charge"],
        "year_drivers": base["drivers"]["years"].get(y, {}),
        "has_detail": any(
            act["months"].get(ym, {}).get("ancillary") for ym in reported),
    }


def decompose(events_plan, events_actual, rate_plan, rate_actual,
              dollar_plan, dollar_actual):
    """Split a revenue miss into event volume, attachment rate and price.

    plan = E_p * A_p * D_p, actual = E_a * A_a * D_a. The three effects below sum
    exactly to (actual - plan), each holding the prior terms at actual and the
    later terms at plan.
    """
    if None in (events_plan, events_actual, rate_plan, rate_actual,
                dollar_plan, dollar_actual):
        return None

    # Where the proforma carried the category at nil, the cascade below would
    # hand the entire result to price -- technically true (D_p is zero) but the
    # wrong story. Nothing was underwritten, so the whole amount is attachment.
    if not rate_plan or not dollar_plan:
        attach = events_actual * rate_actual * dollar_actual
        return {"volume": 0.0, "attach": attach, "price": 0.0,
                "total": attach, "unplanned": True}

    volume = (events_actual - events_plan) * rate_plan * dollar_plan
    attach = events_actual * (rate_actual - rate_plan) * dollar_plan
    price = events_actual * rate_actual * (dollar_actual - dollar_plan)
    return {"volume": volume, "attach": attach, "price": price,
            "total": volume + attach + price, "unplanned": False}
