"""Proforma-refinement signals.

Goal 1 of this analysis is telling how a venue is doing. Goal 2 is telling where
the underwriting model itself is wrong, so the next deal is priced better. That
needs three things a plain variance table does not give:

  bridge      why revenue missed -- fewer events, or less money per event
  persistence a line that misses by 5% every single month is a modelling error,
              a line that misses by 40% once is an incident
  portfolio   the same line missing at every venue is a house assumption to fix
"""
from . import analysis, store

# Lines worth ranking for modelling error. Totals are excluded because they
# double-count their components; the funnel counts and each cost line are in.
# Every component line plus the funnel and the derived rate. Subtotals are
# excluded because they double-count their own components; the blocks they
# summarise are shown separately in the bridge.
SIGNAL_GROUPS = ("funnel", "revenue", "cogs", "payroll", "opex", "adjust")
EXTRA_SIGNAL_KEYS = ["rev_per_event", "rent"]

MATERIAL_PCT = 0.10        # a miss below this is noise for classification
PERSISTENT_MONTHS = 3      # months in a row before a miss is called structural
MATERIAL_FLOOR = 0.005     # a dollar gap under 0.5% of plan revenue is not worth
                           # re-underwriting, however large its percentage


def signal_keys(slug):
    meta = analysis.line_meta(slug)
    keys = [ln["key"] for ln in meta if ln["group"] in SIGNAL_GROUPS]
    present = {ln["key"] for ln in meta}
    keys += [k for k in EXTRA_SIGNAL_KEYS if k in present or k == "rev_per_event"]
    return keys


def _labels(slug):
    out = {ln["key"]: ln for ln in analysis.line_meta(slug)}
    out.setdefault("rev_per_event", {"label": "Revenue / Event", "group": "total",
                                     "format": "usd"})
    out.setdefault("lead_to_contract", {"label": "Lead → Contract Conversion",
                                        "group": "funnel", "format": "pct"})
    return out


def streak(months, key):
    """Consecutive most-recent reported months missing in the same direction."""
    run, direction = 0, 0
    for m in reversed([m for m in months if m["has_actual"]]):
        v = m["var"].get(key, {}).get("var")
        if v is None or v == 0:
            break
        sign = 1 if v > 0 else -1
        if direction == 0:
            direction = sign
        elif sign != direction:
            break
        run += 1
    return run * direction


def revenue_bridge(view):
    """Split the year-to-date total revenue variance into volume and rate."""
    p, a = view["ytd"]["plan"], view["ytd"]["actual"]
    ep, ea = p.get("events"), a.get("events")
    rp, ra = p.get("rev_per_event"), a.get("rev_per_event")
    if None in (ep, ea, rp, ra):
        return None
    volume = (ea - ep) * rp
    rate = ea * (ra - rp)
    return {
        "plan": p.get("total_revenue"), "actual": a.get("total_revenue"),
        "volume": volume, "rate": rate, "total": volume + rate,
        "events_plan": ep, "events_actual": ea,
        "rate_plan": rp, "rate_actual": ra,
    }


def profit_bridge(view):
    """Contribution of each block to the year-to-date profit variance.

    The bottom line differs by venue -- EBITDA after rent at Hadden, Adjusted
    EBITDAR after an adjustments block at Firefly -- so the blocks are taken
    from what the venue actually carries.
    """
    v = view["ytd"]["var"]
    blocks = [("Revenue", "total_revenue"), ("COGS", "total_cogs"),
              ("Payroll", "total_payroll"), ("Operating Expenses", "total_opex"),
              ("Rent", "rent"), ("Other Adjustments", "total_other_adj")]
    steps = [{"label": lbl, "var": v.get(key, {}).get("var")}
             for lbl, key in blocks if key in view["line_keys"] or key.startswith("total")]
    steps = [s for s in steps if s["var"] is not None]
    return {
        "plan": view["ytd"]["plan"].get("profit"),
        "actual": view["ytd"]["actual"].get("profit"),
        "steps": steps,
    }


def classify(pct, run, plan=None, actual=None):
    # A line the proforma zeroed out has no percentage to compute against. That is
    # not missing data -- it is the most interesting case in the model, because it
    # is where the plan said "nothing yet" and the venue did something anyway.
    if pct is None:
        if plan in (0, None) and actual not in (0, None):
            return ("unplanned" if actual > 0 else "unplanned-cost",
                    "Proforma carried nil here")
        return "no-data", "Not reported"
    if abs(run) >= PERSISTENT_MONTHS and abs(pct) >= MATERIAL_PCT:
        return ("structural-under" if pct < 0 else "structural-over",
                f"{abs(run)} months running {'below' if pct < 0 else 'above'} plan")
    if abs(pct) >= 0.25:
        return ("miss" if pct < 0 else "beat"), "Large single-period gap"
    if abs(pct) < MATERIAL_PCT:
        return "on-plan", "Within 10% of plan"
    return ("under" if pct < 0 else "over"), "Modest gap"


def line_signals(slug, year, view=None):
    view = view or analysis.build(slug, year)
    meta = _labels(slug)
    rows = []
    for key in signal_keys(slug):
        if key not in meta:
            continue
        ytd = view["ytd"]["var"].get(key, {})
        plan = view["ytd"]["plan"].get(key)
        actual = view["ytd"]["actual"].get(key)
        if plan is None and actual is None:
            continue
        fmt = meta[key].get("format", "usd")
        rows.append({
            "key": key, "label": meta[key]["label"], "group": meta[key].get("group"),
            "format": fmt, "plan": plan, "actual": actual,
            "var": ytd.get("var"), "pct": ytd.get("pct"),
            "streak": streak(view["months"], key),
            # Rank by dollars at stake, so a 90% miss on a $60 line does not
            # outrank a 12% miss on room rental. Non-dollar lines rank on percent.
            "weight": abs(ytd.get("var") or 0) if fmt == "usd" else 0,
        })

    # Materiality is judged against the size of the business, not the size of the
    # line, so a tenfold overrun on a $100 expense is not dressed up as a finding.
    revenue_scale = abs(view["ytd"]["plan"].get("total_revenue") or 0)
    floor = max(1.0, revenue_scale * MATERIAL_FLOOR)
    for r in rows:
        r["material"] = (r["weight"] >= floor) if r["format"] == "usd" else True
        kind, why = classify(r["pct"], r["streak"], r["plan"], r["actual"])
        if not r["material"] and kind not in ("on-plan", "no-data"):
            kind, why = "immaterial", f"Under {MATERIAL_FLOOR:.1%} of plan revenue"
        r["kind"], r["why"] = kind, why
    rows.sort(key=lambda r: (-r["weight"], -abs(r["pct"] or 0)))
    return rows


def summary(slug, year):
    view = analysis.build(slug, year)
    rows = line_signals(slug, year, view)
    return {
        "view": view,
        "rows": rows,
        "structural": [r for r in rows
                       if r["kind"] in ("structural-under", "structural-over")
                       and r["material"]],
        "unplanned": [r for r in rows
                      if r["kind"].startswith("unplanned") and r["material"]],
        "revenue_bridge": revenue_bridge(view),
        "profit_bridge": profit_bridge(view),
        "ancillary": analysis.ancillary(slug, year),
    }


# ------------------------------------------------------------------ portfolio
def portfolio(year=None):
    """Cross-venue read: which assumptions miss everywhere, not just here.

    Venues are aligned by post-close year rather than calendar date, so a venue
    closed in 2026 and one closed in 2028 are compared at the same point in
    their own life.
    """
    per_line = {}
    venues = []
    for v in store.venues():
        slug = v["slug"]
        yr = year or analysis.current_year(slug)
        if yr not in v["years"]:
            yr = v["years"][0]
        view = analysis.build(slug, yr)
        if not view["n_reported"]:
            venues.append({**v, "year": yr, "n_reported": 0, "rows": []})
            continue
        rows = line_signals(slug, yr, view)
        venues.append({
            **v, "year": yr, "n_reported": view["n_reported"],
            "revenue_var": view["ytd"]["var"].get("total_revenue", {}),
            "profit_var": view["ytd"]["var"].get("profit", {}),
            "events_var": view["ytd"]["var"].get("events", {}),
            "rows": rows,
        })
        for r in rows:
            if r["pct"] is None or not r["material"]:
                continue
            acc = per_line.setdefault(r["key"], {
                "key": r["key"], "label": r["label"], "group": r["group"],
                "format": r["format"], "venues": [], "pcts": [], "vars": [],
            })
            acc["venues"].append({"slug": slug, "venue": v["venue"],
                                  "pct": r["pct"], "var": r["var"],
                                  "kind": r["kind"], "year": yr})
            acc["pcts"].append(r["pct"])
            acc["vars"].append(r["var"] or 0)

    reporting = [v for v in venues if v["n_reported"]]
    consensus = []
    for acc in per_line.values():
        n = len(acc["pcts"])
        under = sum(1 for p in acc["pcts"] if p < -MATERIAL_PCT)
        over = sum(1 for p in acc["pcts"] if p > MATERIAL_PCT)
        acc["n"] = n
        acc["mean_pct"] = sum(acc["pcts"]) / n
        acc["total_var"] = sum(acc["vars"])
        acc["under"] = under
        acc["over"] = over
        # Agreement needs at least two venues. One venue always agrees with
        # itself, and calling that a house assumption would be circular.
        acc["agree"] = n > 1 and (under == n or over == n)
        acc["only_venue"] = n == 1
        # A percentage against a near-nil plan is arithmetically true and
        # useless -- "-48,000%" says nothing a dollar figure does not say
        # better. Suppress it and let the dollars carry the row.
        acc["show_pct"] = abs(acc["mean_pct"]) <= 5.0
        consensus.append(acc)
    # Ranked on dollars at stake, like the venue-level table, with the lines the
    # venues agree on lifted to the top.
    consensus.sort(key=lambda a: (not a["agree"], -abs(a["total_var"])))
    return {"venues": venues, "consensus": consensus, "reporting": reporting}


# ------------------------------------------------------- attachment headlines
HEADLINE_TOP_N = 6


def _headline(cat, cohort):
    """One plain sentence naming the dominant reason a category is off plan."""
    d = cohort.get("decomposition")
    if not d:
        return "Not reported yet."
    if d.get("unplanned"):
        return "Sold, but the proforma carried nothing here."
    effects = [("attach", d["attach"]), ("price", d["price"]), ("volume", d["volume"])]
    name, value = max(effects, key=lambda e: abs(e[1]))
    if abs(value) < 0.05:
        return "On plan."
    rate_p, rate_a = cohort.get("plan_rate"), cohort.get("actual_rate")
    dol_p, dol_a = cohort.get("plan_dollar"), cohort.get("actual_dollar")
    if name == "attach":
        if rate_a == 0:
            return f"Not sold at all — the proforma assumed {rate_p:.0%} of events."
        direction = "more" if value > 0 else "fewer"
        text = (f"Attaching to {direction} events than planned — "
                f"{rate_a:.0%} against {rate_p:.0%}")
        # A large opposing price effect is the whole point of splitting them:
        # "selling it far more often, for far less" is a different instruction to
        # the next proforma than "selling it far more often".
        if d["price"] * value < 0 and abs(d["price"]) > abs(value) * 0.4:
            return text + f", but at {dol_a:,.2f} per event against {dol_p:,.2f}."
        return text + "."
    if name == "price":
        direction = "above" if value > 0 else "below"
        return (f"Attaching about as planned but priced {direction} assumption — "
                f"{dol_a:,.2f} against {dol_p:,.2f} per event.")
    return "Driven by how many events happened, not by this category."


def headline_categories(anc, cohort="new", limit=HEADLINE_TOP_N):
    """The categories worth putting on the overview, largest gap first."""
    rows = []
    for row in anc["rows"]:
        c = row["cohorts"][cohort]
        d = c.get("decomposition")
        if not d:
            continue
        rows.append({**row, "headline": _headline(row, c), "gap": d["total"],
                     # Rank on the category's own behaviour. Event volume moves
                     # every category by the same proportion and is already shown
                     # in the revenue bridge, so including it here would just sort
                     # by category size and bury the ones nobody is selling.
                     "signal": abs(d["attach"]) + abs(d["price"])})
    rows.sort(key=lambda r: -r["signal"])
    return rows[:limit]
