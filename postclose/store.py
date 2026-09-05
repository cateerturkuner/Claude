"""Loading and persistence for post-close analysis data.

Two kinds of file live in DATA_DIR:

  baseline_<slug>.json   the locked pre-acquisition proforma, produced by
                         tools/extract_baseline.py. Never written by the app.
  actuals_<slug>.json    everything reported since close: uploads from finance
                         and manual entries. Written by the app.
"""
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PREVIEW_DIR = os.path.join(DATA_DIR, "previews")
PREVIEW_TTL = 2 * 60 * 60

_lock = threading.Lock()
_baseline_cache = {}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(kind, slug):
    return os.path.join(DATA_DIR, f"{kind}_{slug}.json")


# ------------------------------------------------------------------ baselines
def venues():
    """Every venue with a locked proforma, in close-date order."""
    out = []
    for name in sorted(os.listdir(DATA_DIR)):
        if name.startswith("baseline_") and name.endswith(".json"):
            slug = name[len("baseline_"):-len(".json")]
            b = baseline(slug)
            out.append({
                "slug": slug,
                "venue": b.get("venue", slug),
                "close_month": b.get("close_month"),
                "years": sorted({m["post_close_year"] for m in b["months"]}),
            })
    out.sort(key=lambda v: (v["close_month"] or "", v["venue"]))
    return out


def baseline(slug):
    if slug not in _baseline_cache:
        with open(_path("baseline", slug)) as fh:
            _baseline_cache[slug] = json.load(fh)
    return _baseline_cache[slug]


def has_baseline(slug):
    return os.path.exists(_path("baseline", slug))


# -------------------------------------------------------------------- actuals
def _empty_actuals(slug):
    return {"slug": slug, "months": {}, "events": [], "log": []}


def actuals(slug):
    path = _path("actuals", slug)
    if not os.path.exists(path):
        return _empty_actuals(slug)
    with open(path) as fh:
        data = json.load(fh)
    data.setdefault("months", {})
    data.setdefault("events", [])
    data.setdefault("log", [])
    return data


def save_actuals(slug, data):
    with _lock:
        tmp = _path("actuals", slug) + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, _path("actuals", slug))


def month_slot(data, ym):
    """Get (creating if needed) the record for one actual month."""
    slot = data["months"].setdefault(ym, {})
    slot.setdefault("lines", {})
    slot.setdefault("ancillary", {})
    slot.setdefault("field_source", {})
    return slot


def record(slug, ym, lines, source, ancillary=None, note=None):
    """Merge a month of reported values in.

    `source` is 'upload' or 'manual'. Per-field provenance is kept so the UI can
    show which numbers a person typed over the top of a finance file.
    """
    data = actuals(slug)
    slot = month_slot(data, ym)
    stamp = now_iso()
    for key, value in lines.items():
        if value is None:
            slot["lines"].pop(key, None)
            slot["field_source"].pop(key, None)
            continue
        slot["lines"][key] = value
        slot["field_source"][key] = {"source": source, "at": stamp}
    if ancillary:
        for cat, payload in ancillary.items():
            entry = slot["ancillary"].setdefault(cat, {})
            for k, v in payload.items():
                if v is None:
                    entry.pop(k, None)
                else:
                    entry[k] = v
            if not entry:
                slot["ancillary"].pop(cat, None)
    slot["updated_at"] = stamp
    # An attachment-only save must not relabel a month that came from finance.
    if lines:
        slot["source"] = source
    else:
        slot.setdefault("source", source)
    if note:
        slot["note"] = note
    data["log"].insert(0, {
        "at": stamp, "ym": ym, "source": source,
        "fields": len([v for v in lines.values() if v is not None]),
        "note": note,
    })
    del data["log"][60:]
    save_actuals(slug, data)
    return slot


def delete_month(slug, ym):
    data = actuals(slug)
    if ym in data["months"]:
        del data["months"][ym]
        data["log"].insert(0, {"at": now_iso(), "ym": ym, "source": "deleted",
                               "fields": 0, "note": None})
        save_actuals(slug, data)
        return True
    return False


# ------------------------------------------------------------------- previews
# An upload preview is far too big for a signed session cookie -- four months of
# a P&L already runs to 2.4KB against a ~4KB limit, and a full year would be
# dropped silently, leaving the confirm step reporting an expired preview. So the
# preview lives on disk and only a short token rides in the session.
def _prune_previews():
    if not os.path.isdir(PREVIEW_DIR):
        return
    cutoff = time.time() - PREVIEW_TTL
    for name in os.listdir(PREVIEW_DIR):
        path = os.path.join(PREVIEW_DIR, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.unlink(path)
        except OSError:
            pass


def put_preview(payload):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    _prune_previews()
    token = secrets.token_urlsafe(16)
    with open(os.path.join(PREVIEW_DIR, token + ".json"), "w") as fh:
        json.dump(payload, fh)
    return token


def get_preview(token):
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", token):
        return None
    path = os.path.join(PREVIEW_DIR, token + ".json")
    if not os.path.exists(path) or os.path.getmtime(path) < time.time() - PREVIEW_TTL:
        return None
    with open(path) as fh:
        return json.load(fh)


def drop_preview(token):
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", token):
        return
    try:
        os.unlink(os.path.join(PREVIEW_DIR, token + ".json"))
    except OSError:
        pass
