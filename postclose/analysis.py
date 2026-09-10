"""Variance analysis: reported actuals against the locked proforma.

Sign convention. Every cost line in the source model is carried as a negative
number, so `actual - plan` is favourable when positive for *every* line in the
P&L, funnel and conversion set alike. Nothing needs a per-line sign flip.

Periods. "Year" always means a post-close year (Y1 = the twelve months from the
close month), never a calendar year. The month -> year mapping is taken from the
baseline workbook itself rather than recomputed.
"""
from datetime import date

from . import lines as lines_module
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

def headlines(base):
    """Tiles for the overview. The profit line differs by venue -- Hadden ends at
    EBITDA, Firefly at Adjusted EBITDAR -- so it is read from the baseline."""
    profit = base.get("profit_key") or "ebitdar"
    label = next((ln["label"] for ln in base["lines"] if ln["key"] == profit),
                 "Profit")
    return [("total_revenue", "Total Revenue", "usd"),
            (profit, label, "usd"),
            ("events", "Events", "count"),
            ("rev_per_event", "Revenue / Event", "usd")]


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


def subtotal_rules(lines_meta):
    """(key, component keys) pairs for this venue, in dependency order.

    Built from the baseline's own line groups rather than a fixed list, so a
    venue that carries all-inclusive revenue, a corporate payroll line or an
    adjustments block rolls those into the right subtotal without a code change.
    """
    present = {ln["key"] for ln in lines_meta}
    by_group = {}
    for ln in lines_meta:
        by_group.setdefault(ln["group"], []).append(ln["key"])

    rules = []
    for key, group in lines_module.SUBTOTAL_GROUPS:
        members = by_group.get(group, [])
        if members:
            rules.append((key, members))
    for key, components in lines_module.SUBTOTAL_SUMS:
        if all(c in present or any(c == k for k, _ in rules) for c in components):
            rules.append((key, components))

    order = [k for k, _ in lines_module.SUBTOTAL_GROUPS]
    order += [k for k, _ in lines_module.SUBTOTAL_SUMS]
    rules.sort(key=lambda r: order.index(r[0]))
    return rules


def fill_subtotals(bucket, rules, derived_keys=None):
    """Compute any subtotal the source did not supply, from its components.

    Finance packages routinely omit Gross Margin or EBITDA, or stop at Total
    Revenue. Without this, those rows read as "not reported" even though every
    component arrived. Rules are in dependency order, so EBITDA can be built on
    a Gross Margin that was itself just derived.
    """
    derived = derived_keys if derived_keys is not None else set()
    for key, components in rules:
        if bucket.get(key) is not None:
            continue
        value = _sum(bucket.get(c) for c in components)
        if value is not None:
            bucket[key] = value
            derived.add(key)
    return bucket


def add_derived(bucket, profit_key="ebitda"):
    """Attach ratio metrics that are computed from other lines, not summed."""
    bucket["rev_per_event"] = _safe_div(bucket.get("total_revenue"),
                                        bucket.get("events"))
    bucket["profit"] = bucket.get(profit_key)
    bucket["profit_margin"] = _safe_div(bucket.get(profit_key),
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


def has_segments(slug):
    """True when the venue is really more than one venue sharing a cost base."""
    segs = store.baseline(slug).get("segments", [])
    return len(segs) > 1


def segments(slug):
    return store.baseline(slug).get("segments", [])


def build(slug, year, segment=None):
    """Everything the month / YTD / full-year views need for one post-close year.

    `segment` restricts the funnel and event counts to one segment. Costs are
    always venue-level -- Firefly's Barn and Chapel share a single cost base --
    so a segmented view carries segment events against venue expenses, and the
    UI is responsible for not implying otherwise.
    """
    base = store.baseline(slug)
    act = store.actuals(slug)
    keys = [ln["key"] for ln in base["lines"]]
    profit_key = base.get("profit_key") or "ebitdar"
    rules = subtotal_rules(base["lines"])
    segs = base.get("segments", [])
    seg_keys = [s["key"] for s in segs]

    months = []
    for m in base["months"]:
        if m["post_close_year"] != year:
            continue
        reported = act["months"].get(m["ym"], {})
        plan_lines = {k: m["lines"].get(k) for k in keys}
        actual_lines = dict(reported.get("lines", {}))
        has_actual = bool(actual_lines)

        # Firefly carries no venue-level Events row -- every event belongs to
        # the Barn, the Chapel or an elopement. Where the model has no venue
        # total, it is the sum of the segments.
        for role in ("contracts", "events_oc", "events_new", "events"):
            if plan_lines.get(role) is None and seg_keys:
                plan_lines[role] = _sum(
                    (m.get("segments", {}).get(k) or {}).get(role) for k in seg_keys)
            if has_actual and actual_lines.get(role) is None:
                rep_segs = reported.get("segments", {}) or {}
                actual_lines[role] = _sum(
                    (rep_segs.get(k) or {}).get(role) for k in seg_keys)

        # A segment view swaps the venue-wide funnel counts for that segment's.
        if segment:
            for role, value in (m.get("segments", {}).get(segment) or {}).items():
                plan_lines[role] = value
            rep_seg = (reported.get("segments", {}) or {}).get(segment, {})
            for role in ("contracts", "events_oc", "events_new", "events"):
                actual_lines.pop(role, None)
                if rep_seg.get(role) is not None:
                    actual_lines[role] = rep_seg[role]

        plan = add_derived(plan_lines, profit_key)
        derived_keys = set()
        actual = {}
        if has_actual:
            actual = add_derived(
                fill_subtotals(actual_lines, rules, derived_keys), profit_key)
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
            "plan_segments": m.get("segments", {}),
            "note": reported.get("note"),
        })

    closed = [m for m in months if m["has_actual"]]
    open_months = [m for m in months if not m["has_actual"]]

    # Keys the proforma carries, the funnel roles, plus anything actually
    # reported that the proforma has no line for -- Firefly's rent, for
    # instance. Without that last part a line we never underwrote would be
    # dropped rather than flagged as unplanned.
    reported_keys = {k for m in months for k in (m["actual"] or {})}
    roll_keys = list(dict.fromkeys(
        keys + ["contracts", "events_oc", "events_new", "events", "rent"]
        + sorted(reported_keys)))

    # Year to date: plan restated over exactly the months that have reported.
    ytd_plan = add_derived({k: _sum(m["plan"].get(k) for m in closed)
                            for k in roll_keys}, profit_key)
    ytd_actual = add_derived({k: _sum(m["actual"].get(k) for m in closed)
                              for k in roll_keys}, profit_key)

    # Full year: plan for all twelve, and a projection that keeps reported months
    # and falls back to plan for months not yet closed.
    fy_plan = add_derived({k: _sum(m["plan"].get(k) for m in months)
                           for k in roll_keys}, profit_key)
    fy_proj = add_derived({
        k: _sum([m["actual"].get(k) for m in closed] + [m["plan"].get(k) for m in open_months])
        for k in roll_keys
    }, profit_key)

    all_keys = list(fy_plan.keys())
    return {
        "slug": slug,
        "venue": base["venue"],
        "year": year,
        "profit_key": profit_key,
        "profit_label": next((ln["label"] for ln in base["lines"]
                              if ln["key"] == profit_key), "Profit"),
        "segments": segs,
        "segment": segment,
        "segment_label": next((s["label"] for s in segs if s["key"] == segment), None),
        "headlines": headlines(base),
        "line_keys": keys,
        "years": years_available(slug),
        "close_month": base["close_month"],
        "lines": base["lines"],
        "months": months,
        "reported_months": [m["ym"] for m in closed],
        # Where each reported month came from, so a figure entered as a stand-in
        # is not read as measured.
        "provenance": [{"ym": m["ym"], "label": m["label"], "source": m["source"],
                        "note": m["note"]} for m in closed],
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
def attachment_segments(slug):
    """Segments that have attachment drivers. Elopements, for instance, has
    contracts and events in the model but no Revenue Analysis tab."""
    return [s for s in store.baseline(slug).get("segments", []) if s["drivers"]]


def ancillary(slug, year, segment=None):
    """Attachment rate and $/attached-event, proforma vs reported, per segment.

    The proforma states these annually, so reported figures are rolled to a
    year-to-date rate and compared against the annual assumption. Where only
    revenue was reported, attachment is left blank rather than guessed.
    """
    base = store.baseline(slug)
    act = store.actuals(slug)
    with_drivers = attachment_segments(slug)
    if not with_drivers:
        return None
    seg = next((s for s in with_drivers if s["key"] == segment), with_drivers[0])
    drivers = seg["drivers"]
    y = str(year)

    view = build(slug, year, segment=seg["key"])
    reported = view["reported_months"]
    plan_by_ym = {m["ym"]: m for m in base["months"]}

    events_actual = {"oc": 0.0, "new": 0.0}
    events_plan = {"oc": 0.0, "new": 0.0}
    for ym in reported:
        rep = (act["months"].get(ym, {}).get("segments", {}) or {}).get(seg["key"], {})
        pl = (plan_by_ym.get(ym, {}).get("segments", {}) or {}).get(seg["key"], {})
        for cohort, role in (("oc", "events_oc"), ("new", "events_new")):
            events_actual[cohort] += rep.get(role) or 0
            events_plan[cohort] += pl.get(role) or 0

    rows = []
    for cat in drivers["categories"]:
        rep = {}
        for ym in reported:
            entry = ((act["months"].get(ym, {}).get("ancillary", {}) or {})
                     .get(seg["key"], {}).get(cat["key"], {}))
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
        "segment": seg["key"],
        "segment_label": seg["label"],
        "segments": with_drivers,
        "events_plan": events_plan,
        "events_actual": events_actual,
        "reported_months": reported,
        "service_charge": drivers["service_charge"],
        "year_drivers": drivers["years"].get(y, {}),
        "has_detail": any(
            (act["months"].get(ym, {}).get("ancillary", {}) or {}).get(seg["key"])
            for ym in reported),
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


# ------------------------------------------------------------------- segments
def segment_summary(slug, year):
    """Per-segment contracts, events and revenue per event.

    Contracts and events compare against the proforma month by month, because
    the model carries both monthly. Revenue does not: the model splits revenue
    by segment only annually, so the comparison shown is $ per event -- a rate,
    which is comparable against an annual assumption -- rather than a revenue
    level, which would mean inventing a monthly plan the model never stated.
    """
    base = store.baseline(slug)
    act = store.actuals(slug)
    segs = base.get("segments", [])
    if len(segs) < 2:
        return None

    view = build(slug, year)
    reported = view["reported_months"]
    y = str(year)

    rows = []
    for seg in segs:
        sv = build(slug, year, segment=seg["key"])

        # The proforma's $/event rate is built from the Revenue Analysis
        # categories only. Firefly also sells all-inclusive packages and
        # elopements, which the model carries as their own P&L lines and leaves
        # out of that rate -- so they are excluded from the comparable figure
        # and reported separately, rather than inflating a rate they were never
        # part of.
        comparable_cats = ({c["key"] for c in seg["drivers"]["categories"]}
                           | {"service_charge"}) if seg["drivers"] else set()
        revenue = 0.0
        comparable = 0.0
        seen = False
        for ym in reported:
            cats = (act["months"].get(ym, {}).get("ancillary", {}) or {}).get(
                seg["key"], {})
            for cat, payload in cats.items():
                for k, v in payload.items():
                    if not k.endswith("_rev") or not isinstance(v, (int, float)):
                        continue
                    revenue += v
                    seen = True
                    if cat in comparable_cats:
                        comparable += v
        events = sv["ytd"]["actual"].get("events")
        plan_rate = (seg["drivers"]["years"][y].get("rev_per_event_total")
                     if seg["drivers"] else None)
        rows.append({
            "key": seg["key"], "label": seg["label"],
            "has_attachment": bool(seg["drivers"]),
            "contracts": {"plan": sv["ytd"]["plan"].get("contracts"),
                          "actual": sv["ytd"]["actual"].get("contracts"),
                          "var": sv["ytd"]["var"].get("contracts", {})},
            "events": {"plan": sv["ytd"]["plan"].get("events"),
                       "actual": events,
                       "var": sv["ytd"]["var"].get("events", {})},
            "events_oc": sv["ytd"]["actual"].get("events_oc"),
            "events_new": sv["ytd"]["actual"].get("events_new"),
            "revenue": revenue if seen else None,
            "outside_rate": (revenue - comparable) if seen else None,
            # A space with no Revenue Analysis tab has no comparable revenue and
            # no rate to compare against. Reporting 0.00 would read as "we earned
            # nothing per event" rather than "there is nothing to compare".
            "rev_per_event": (_safe_div(comparable, events)
                              if seen and comparable_cats else None),
            "plan_rev_per_event": plan_rate,
            "rate_var": variance(_safe_div(comparable, events) if comparable_cats
                                 else None, plan_rate),
        })
    return {"rows": rows, "reported": reported,
            "revenue_total": _sum(r["revenue"] for r in rows)}
