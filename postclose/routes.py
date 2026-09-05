"""Blueprint: post-close performance vs. the pre-acquisition proforma."""
import os
import tempfile

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   session, url_for, jsonify)

from . import analysis, ingest, signals, store

bp = Blueprint("postclose", __name__,
               template_folder="templates", url_prefix="/PostCloseAnalysis")

PREVIEW_KEY = "postclose_preview"

# Tab id -> endpoint, so the venue/year switchers can keep you on the tab you are on.
TAB_ENDPOINTS = {
    "overview": "postclose.overview",
    "funnel": "postclose.funnel",
    "pnl": "postclose.pnl",
    "ancillary": "postclose.ancillary",
    "signals": "postclose.venue_signals",
    "data": "postclose.data",
    "portfolio": "postclose.overview",
}


# ------------------------------------------------------------------- filters
def fmt_num(value, dp=1):
    if value is None:
        return "–"
    return f"{value:,.{dp}f}"


def fmt_k(value, dp=1):
    """Money held in thousands, rendered compactly."""
    if value is None:
        return "–"
    if abs(value) >= 1000:
        return f"${value / 1000:,.2f}m"
    return f"${value:,.{dp}f}k"


def fmt_count(value):
    if value is None:
        return "–"
    return f"{value:,.0f}" if abs(value - round(value)) < 0.05 else f"{value:,.1f}"


def fmt_pct(value, dp=1):
    if value is None:
        return "–"
    return f"{value * 100:,.{dp}f}%"


def fmt_by(value, kind, dp=1):
    if kind == "pct":
        return fmt_pct(value)
    if kind == "count":
        return fmt_count(value)
    return fmt_num(value, dp)


def fmt_signed(value, kind="usd", dp=1):
    if value is None:
        return "–"
    body = fmt_by(abs(value), kind, dp)
    return f"{'+' if value >= 0 else '−'}{body}"


def tone(value, threshold=0.0):
    """Favourable / unfavourable class. Positive is favourable on every line."""
    if value is None:
        return "flat"
    if value > threshold:
        return "good"
    if value < -threshold:
        return "bad"
    return "flat"


bp.add_app_template_filter(fmt_num, "num")
bp.add_app_template_filter(fmt_k, "money")
bp.add_app_template_filter(fmt_count, "count")
bp.add_app_template_filter(fmt_pct, "pct")
bp.add_app_template_filter(fmt_signed, "signed")
bp.add_app_template_global(fmt_by, "fmt_by")
bp.add_app_template_global(fmt_signed, "fmt_signed")
bp.add_app_template_global(tone, "tone")
bp.add_app_template_global(analysis.GROUP_LABELS, "GROUP_LABELS")
bp.add_app_template_global(analysis.HEADLINES, "HEADLINES")
bp.add_app_template_global(TAB_ENDPOINTS, "TAB_ENDPOINTS")


# --------------------------------------------------------------------- helpers
def _ctx(slug):
    if not store.has_baseline(slug):
        abort(404)
    vs = store.venues()
    year = request.args.get("year", type=int) or analysis.current_year(slug)
    if year not in analysis.years_available(slug):
        year = analysis.years_available(slug)[0]
    return {"slug": slug, "venues": vs, "year": year,
            "venue": next(v for v in vs if v["slug"] == slug)}


def _first_slug():
    vs = store.venues()
    if not vs:
        abort(404, "No venue proforma has been loaded yet.")
    return vs[0]["slug"]


# ----------------------------------------------------------------------- views
@bp.route("/")
def index():
    return redirect(url_for("postclose.overview", slug=_first_slug()))


@bp.route("/<slug>/")
@bp.route("/<slug>/overview")
def overview(slug):
    ctx = _ctx(slug)
    view = analysis.build(slug, ctx["year"])
    return render_template("postclose/overview.html", tab="overview", view=view,
                           bridge=signals.revenue_bridge(view),
                           ebitda=signals.ebitda_bridge(view), **ctx)


@bp.route("/<slug>/funnel")
def funnel(slug):
    ctx = _ctx(slug)
    view = analysis.build(slug, ctx["year"])
    return render_template("postclose/funnel.html", tab="funnel", view=view, **ctx)


@bp.route("/<slug>/pnl")
def pnl(slug):
    ctx = _ctx(slug)
    view = analysis.build(slug, ctx["year"])
    return render_template("postclose/pnl.html", tab="pnl", view=view,
                           mode=request.args.get("mode", "variance"), **ctx)


@bp.route("/<slug>/ancillary")
def ancillary(slug):
    ctx = _ctx(slug)
    return render_template("postclose/ancillary.html", tab="ancillary",
                           view=analysis.build(slug, ctx["year"]),
                           anc=analysis.ancillary(slug, ctx["year"]), **ctx)


@bp.route("/<slug>/signals")
def venue_signals(slug):
    ctx = _ctx(slug)
    return render_template("postclose/signals.html", tab="signals",
                           **signals.summary(slug, ctx["year"]), **ctx)


@bp.route("/portfolio")
def portfolio():
    slug = _first_slug()
    year = request.args.get("year", type=int)
    return render_template("postclose/portfolio.html", tab="portfolio",
                           slug=slug, venues=store.venues(), year=year,
                           venue=next(v for v in store.venues() if v["slug"] == slug),
                           data=signals.portfolio(year))


# ------------------------------------------------------------------------ data
@bp.route("/<slug>/data")
def data(slug):
    ctx = _ctx(slug)
    view = analysis.build(slug, ctx["year"])
    act = store.actuals(slug)

    # Which month the by-hand form is editing. Defaults to the last month that has
    # actuals, else the first month of the year still open.
    edit_ym = request.args.get("ym")
    if edit_ym not in {mo["ym"] for mo in view["months"]}:
        edit_ym = (view["reported_months"][-1] if view["reported_months"]
                   else view["months"][0]["ym"])
    edit_month = next(mo for mo in view["months"] if mo["ym"] == edit_ym)

    return render_template(
        "postclose/data.html", tab="data", view=view, actuals=act,
        preview=store.get_preview(session.get(PREVIEW_KEY, {}).get(slug)),
        edit_ym=edit_ym, edit_month=edit_month,
        edit_month_anc=act["months"].get(edit_ym, {}).get("ancillary", {}),
        categories=store.baseline(slug)["drivers"]["categories"], **ctx)


@bp.route("/<slug>/upload", methods=["POST"])
def upload(slug):
    ctx = _ctx(slug)
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("postclose.data", slug=slug, year=ctx["year"]))
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        flash("Upload an .xlsx or .xlsm workbook.", "error")
        return redirect(url_for("postclose.data", slug=slug, year=ctx["year"]))

    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        file.save(path)
        prev = ingest.preview(path, slug, sheet=request.form.get("sheet") or None)
    finally:
        os.unlink(path)

    if not prev.get("ok"):
        flash(prev.get("error", "Could not read that workbook."), "error")
        return redirect(url_for("postclose.data", slug=slug, year=ctx["year"]))

    prev["filename"] = file.filename
    cache = session.get(PREVIEW_KEY, {})
    store.drop_preview(cache.get(slug))
    cache[slug] = store.put_preview(prev)
    session[PREVIEW_KEY] = cache
    return redirect(url_for("postclose.data", slug=slug, year=ctx["year"]) + "#preview")


@bp.route("/<slug>/upload/confirm", methods=["POST"])
def upload_confirm(slug):
    ctx = _ctx(slug)
    cache = session.get(PREVIEW_KEY, {})
    prev = store.get_preview(cache.get(slug))
    if not prev:
        flash("That preview expired. Upload the file again.", "error")
        return redirect(url_for("postclose.data", slug=slug, year=ctx["year"]))

    months = set(request.form.getlist("month"))
    scale = float(request.form.get("scale") or 1.0)
    written = ingest.apply_preview(
        slug, prev,
        include_keys=request.form.getlist("key"),
        months=months, scale=scale,
        flip_costs=request.form.get("flip_costs") == "on",
        filename=prev.get("filename"),
    )

    # The event list is applied second on purpose: where both sheets carry event
    # counts, one row per event is the more reliable of the two.
    events_written = []
    if prev.get("events") and request.form.get("import_events") == "on":
        events_written = ingest.apply_events(
            slug, prev["events"], months, scale=scale, filename=prev.get("filename"))

    touched = sorted(set(written) | set(events_written))
    detail = ", ".join(analysis.ym_label(m) for m in touched) or "nothing"
    extra = (f" Event detail for {len(events_written)} month(s)."
             if events_written else "")
    flash(f"Imported {len(touched)} month(s): {detail}.{extra}", "ok")
    return redirect(url_for("postclose.overview", slug=slug, year=ctx["year"]))


@bp.route("/<slug>/upload/cancel", methods=["POST"])
def upload_cancel(slug):
    cache = session.get(PREVIEW_KEY, {})
    store.drop_preview(cache.pop(slug, None))
    session[PREVIEW_KEY] = cache
    return redirect(url_for("postclose.data", slug=slug))


@bp.route("/<slug>/manual", methods=["POST"])
def manual(slug):
    ctx = _ctx(slug)
    ym = request.form.get("ym")
    if not ym:
        flash("Pick a month.", "error")
        return redirect(url_for("postclose.data", slug=slug, year=ctx["year"]))

    lines, ancillary_in = {}, {}
    for field, raw in request.form.items():
        if not field.startswith(("line__", "anc__")):
            continue
        raw = (raw or "").strip().replace(",", "").replace("$", "")
        value = None
        if raw != "":
            try:
                value = float(raw.rstrip("%")) / (100 if raw.endswith("%") else 1)
            except ValueError:
                flash(f"'{raw}' in {field} is not a number — skipped.", "error")
                continue
        if field.startswith("line__"):
            lines[field[len("line__"):]] = value
        else:
            _, cat, metric = field.split("__", 2)
            ancillary_in.setdefault(cat, {})[metric] = value

    store.record(slug, ym, lines, "manual", ancillary=ancillary_in,
                 note=request.form.get("note") or None)
    flash(f"Saved {analysis.ym_label(ym)}.", "ok")
    return redirect(url_for("postclose.data", slug=slug, year=ctx["year"]))


@bp.route("/<slug>/month/<ym>/delete", methods=["POST"])
def month_delete(slug, ym):
    ctx = _ctx(slug)
    if store.delete_month(slug, ym):
        flash(f"Cleared {analysis.ym_label(ym)}.", "ok")
    return redirect(url_for("postclose.data", slug=slug, year=ctx["year"]))


# ------------------------------------------------------------------------- api
@bp.route("/api/<slug>/<int:year>.json")
def api_year(slug, year):
    if not store.has_baseline(slug):
        abort(404)
    return jsonify(analysis.build(slug, year))
