"""Sample data and reference rules for the frontend.

Everything here is demo data so the templates render. The backend developer
should replace each function with real queries. The *rules* (thresholds,
formulas) are the ones the product design uses, so keep them.

Business rules used by the design
---------------------------------
- Hen-day production % = eggs collected today / live birds today * 100.
- Production status: >= 85% on target (green), 75-85% below target (amber),
  < 75% sharp drop (red).
- Layers start laying at about 16 weeks. A batch becomes "Laying"
  automatically once production reaches 5%.
- Layers are retired at about 18 months (78 weeks). Plan replacement chicks
  16 weeks before retirement.
- Mortality spike alert: more than 0.5% of live birds in one day.
- A vaccine can carry a withdrawal period (days). While it runs, eggs from
  that batch must not be sold.
- One crate = 30 eggs.
"""
import math
from datetime import date, timedelta

LIVE_BIRDS = 988  # Batch A hens, used for the hen-day ratio
TARGET_PCT = 85

BATCHES = {
    "A": {"code": "A", "name": "Batch A · Layers", "short": "Batch A", "sub": "988 hens · week 26 · laying", "age": "Week 26"},
    "B": {"code": "B", "name": "Batch B · Layers", "short": "Batch B", "sub": "600 pullets · week 14 · rearing", "age": "Week 14"},
    "C": {"code": "C", "name": "Batch C · Layers", "short": "Batch C", "sub": "493 chicks · week 3 · brooding", "age": "Week 3"},
}


# ---------------------------------------------------------------- eggs ----
def egg_summary(good, cracked, dirty, birds=LIVE_BIRDS):
    """Reference implementation of the production card."""
    total = good + cracked + dirty
    pct = (total / birds * 100) if birds else 0.0
    if pct >= 85:
        status, label, tone = "on_target", "On target", "success"
    elif pct >= 75:
        status, label, tone = "below", "Below target", "warning"
    else:
        status, label, tone = "drop", "Sharp drop · check the flock", "danger"
    delta = pct - 88.0  # 88.0 = yesterday's value in the demo

    def share(n):
        return round(n / total * 100, 1) if total else 0

    pct = round(pct, 1)
    return {
        "good": good, "cracked": cracked, "dirty": dirty,
        "total": total, "birds": birds,
        "pct": pct, "fill": min(100, pct),
        "status": status, "label": label, "tone": tone,
        "delta_text": f"{'▲' if delta >= 0 else '▼'} {abs(delta):.1f} pts vs yesterday",
        "good_pct": share(good), "cracked_pct": share(cracked), "dirty_pct": share(dirty),
        "crates": good // 30, "loose": good % 30,
    }


_BASE = date(2026, 8, 25)  # first laying day of Batch A in the demo
_TAIL = [86.7, 87.4, 87.9, 88.2, 87.6, 88.0, 88.8]


def _series():
    n = 64
    out = []
    for i in range(n):
        if i < 35:
            v = 4 + 83 / (1 + math.exp(-(i - 15) / 4.2))
        else:
            v = 86.5 + (i - 35) * 0.06
        v += math.sin(i * 1.9) * 0.8 + math.cos(i * 0.7) * 0.5
        out.append(v)
    out[50] = 79.4
    out[51] = 84.1
    for k in range(7):
        out[n - 7 + k] = _TAIL[k]
    return [{"i": i, "date": _BASE + timedelta(days=i), "v": round(v, 1)} for i, v in enumerate(out)]


def _lab(d):
    return f"{d:%b} {d.day}"


def history(range_key="30"):
    """Production history. range_key: '7', '30' or 'all'."""
    if range_key not in ("7", "30", "all"):
        range_key = "30"
    allp = _series()
    n_all = len(allp)
    pts = allp[n_all - 7:] if range_key == "7" else allp[n_all - 30:] if range_key == "30" else allp
    y_min = 0 if range_key == "all" else 60

    bars = []
    for p in pts:
        h = max(2.0, (p["v"] - y_min) / (100 - y_min) * 100)
        bars.append({
            "label": _lab(p["date"]), "v": p["v"], "h": round(h, 1),
            "dip": p["i"] >= 35 and p["v"] < 82, "below": p["v"] < 85,
        })

    avg = sum(p["v"] for p in pts) / len(pts)
    best = max(pts, key=lambda p: p["v"])
    eggs = sum(round(p["v"] / 100 * LIVE_BIRDS) for p in pts)

    x_labels = [_lab(pts[round(j * (len(pts) - 1) / 4)]["date"]) for j in range(5)]

    def mean(seg):
        return sum(p["v"] for p in seg) / len(seg)

    weeks = []
    for w in range(4):
        end = n_all - 7 * w
        start = end - 7
        seg = allp[start:end]
        prev = allp[start - 7:start]
        a = mean(seg)
        d = a - mean(prev) if len(prev) == 7 else 0
        if d >= 0.05:
            tone, text = "success", f"▲ {d:.1f}"
        elif d <= -0.05:
            tone, text = "warning", f"▼ {abs(d):.1f}"
        else:
            tone, text = "neutral", "– 0.0"
        weeks.append({
            "label": f"{_lab(seg[0]['date'])} – {_lab(seg[-1]['date'])}",
            "avg": round(a, 1), "ok": a >= 85, "delta_tone": tone, "delta_text": text,
        })

    ranges = [("7", "7 days"), ("30", "30 days"), ("all", "All time")]
    return {
        "range": range_key,
        "ranges": [{"key": k, "label": l, "active": k == range_key} for k, l in ranges],
        "bars": bars,
        "x_labels": x_labels,
        "y_labels": ["100", "75", "50", "25", "0"] if range_key == "all" else ["100", "90", "80", "70", "60"],
        "target_pos": round((85 - y_min) / (100 - y_min) * 100, 1),
        "avg": round(avg, 1),
        "best": {"v": best["v"], "label": _lab(best["date"])},
        "on_target": sum(1 for p in pts if p["v"] >= 85),
        "days": len(pts),
        "eggs": eggs,
        "crates": round(eggs * 0.96) // 30,
        "range_label": f"{_lab(pts[0]['date'])} – {_lab(pts[-1]['date'])}, 2026",
        "weeks": weeks,
    }


# ----------------------------------------------------------- dashboard ----
NEXT_ACTIONS = [
    {"tone": "danger", "icon": "exclamation-triangle-fill", "title": "Give Lasota booster", "detail": "Batch B pullets · 14 days overdue", "pill": "Now", "url_name": "vaccines"},
    {"tone": "warning", "icon": "eyedropper", "title": "Vaccinate Batch C chicks", "detail": "Lasota, week 3", "pill": "Today", "url_name": "vaccines"},
    {"tone": "warning", "icon": "clock-history", "title": "Hold Batch A egg sales", "detail": "Vaccine withdrawal ends Nov 1", "pill": "5 days", "url_name": "vaccines"},
    {"tone": "success", "icon": "egg", "title": "Prepare Batch B for laying", "detail": "Laying house + EDS vaccine by Nov 3", "pill": "7 days", "url_name": "batches"},
    {"tone": "neutral", "icon": "basket", "title": "Reorder grower mash", "detail": "About 11 days of stock left", "pill": "11 days", "url_name": "feed"},
]

BATCH_CARDS = [
    {
        "code": "A", "name": "Batch A", "stage": "Laying", "stage_tone": "success",
        "sub": "988 hens · week 26 · hatched Apr 28", "big": "52 wks", "big_label": "of life left",
        "marker": 33.3,
        "chips": [("Production 88.8% · above target", "success"), ("Deaths today 2", "neutral")],
        "next": "Order replacement chicks by Jul 7, 2027 so they start laying when Batch A retires in Oct 2027.",
        "url_name": "eggs",
    },
    {
        "code": "B", "name": "Batch B", "stage": "Rearing", "stage_tone": "warning",
        "sub": "600 pullets · week 14 · hatched Jul 21", "big": "14 days", "big_label": "to first eggs",
        "marker": 17.9,
        "chips": [("Weight 1.31 kg · on target", "success"), ("Uniformity 84%", "success")],
        "next": "By Nov 3: move to the laying house and give the EDS vaccine. Status becomes Laying automatically at 5% production.",
        "url_name": "vaccines",
    },
    {
        "code": "C", "name": "Batch C", "stage": "Brooding", "stage_tone": "brood",
        "sub": "493 chicks · week 3 · hatched Oct 6", "big": "91 days", "big_label": "to first eggs",
        "marker": 3.8,
        "chips": [("Weight 0.23 kg · on target", "success"), ("Uniformity 86%", "success")],
        "next": "Give the Lasota vaccine today. Move out of the brooder at week 6 (Nov 17) and switch to grower mash at week 8 (Dec 1).",
        "url_name": "vaccines",
    },
]


# ----------------------------------------------------------------- feed ----
FEED_TODAY = [
    {"batch": "Batch A · Layers mash", "detail": "113.6 kg (4.5 bags) · 988 birds", "g": 115, "tone": "success", "note": "Within the usual 110 – 120 g range for layers"},
    {"batch": "Batch B · Grower mash", "detail": "54.0 kg (2.2 bags) · 600 birds", "g": 90, "tone": "neutral", "note": ""},
    {"batch": "Batch C · Chick mash", "detail": "17.3 kg (0.7 bag) · 493 chicks", "g": 35, "tone": "neutral", "note": ""},
]

FEED_STOCK = [
    {"name": "Layers mash", "bags": 62, "expires": "Jan 15, 2027", "days_left": 13, "pct": 45, "tone": "success", "flag": ""},
    {"name": "Grower mash", "bags": 24, "expires": "Dec 20, 2026", "days_left": 11, "pct": 37, "tone": "warning", "flag": "Reorder soon"},
    {"name": "Chick mash", "bags": 12, "expires": "Mar 2, 2027", "days_left": 17, "pct": 55, "tone": "success", "flag": ""},
]


# --------------------------------------------------------------- health ----
def _row(pk, kind, name, sub):
    return {"pk": pk, "kind": kind, "name": name, "sub": sub}


VACCINES = {
    "A": {
        "withdrawal": {"tone": "warning", "big": "5 days left", "progress": 28.6,
                       "text": "Vaccine given Oct 25 with a 7-day withdrawal. Do not sell eggs from this batch until Nov 1."},
        "rows": [
            _row(101, "pending", "Lasota booster · Week 38", "Due Jan 19, 2027"),
            _row(102, "done", "Lasota booster · Week 26", "Oct 25"),
            _row(103, "done", "Egg Drop Syndrome · before laying", "Aug 11"),
            _row(104, "done", "Lasota booster · Week 12", "Jul 21"),
            _row(105, "done", "Lasota · Week 6", "Jun 9"),
            _row(106, "done", "Gumboro · Week 4", "May 26"),
            _row(107, "done", "Lasota · Week 3", "May 19"),
            _row(108, "done", "Gumboro · Week 2", "May 12"),
            _row(109, "done", "Marek's · Day 1", "Apr 28"),
        ],
    },
    "B": {
        "withdrawal": {"tone": "success", "big": "None active", "progress": None,
                       "text": "No hold on this batch. The pullets are not laying yet, so no eggs are affected."},
        "rows": [
            _row(201, "overdue", "Lasota booster · Week 12", "Was due Oct 13 · 14 days overdue"),
            _row(202, "pending", "Egg Drop Syndrome · before laying", "Due Nov 3"),
            _row(203, "done", "Lasota · Week 6", "Sep 1"),
            _row(204, "done", "Gumboro · Week 4", "Aug 18"),
            _row(205, "done", "Lasota · Week 3", "Aug 11"),
            _row(206, "done", "Gumboro · Week 2", "Aug 4"),
            _row(207, "done", "Marek's · Day 1", "Jul 21"),
        ],
    },
    "C": {
        "withdrawal": {"tone": "success", "big": "None active", "progress": None,
                       "text": "No hold on this batch. The chicks are months from laying, so no eggs are affected."},
        "rows": [
            _row(301, "pending", "Lasota · Week 3", "Due today, Oct 27"),
            _row(302, "pending", "Gumboro · Week 4", "Due Nov 3"),
            _row(303, "pending", "Lasota · Week 6", "Due Nov 17"),
            _row(304, "done", "Gumboro · Week 2", "Oct 20"),
            _row(305, "done", "Marek's · Day 1", "Oct 6"),
        ],
    },
}


def clean_batch(code):
    return code if code in BATCHES else "A"


def vaccine_panel(code):
    code = clean_batch(code)
    data = VACCINES[code]
    return {"batch": BATCHES[code], "withdrawal": data["withdrawal"], "rows": data["rows"]}


def mark_given(pk):
    for data in VACCINES.values():
        for r in data["rows"]:
            if r["pk"] == pk:
                r["kind"] = "done"
                r["sub"] = "Given today"
                return r
    return None


MORTALITY = {
    "A": {"den": 988, "spike_min": 5, "counts": [6, 1, 0, 2, 1, 0, 2], "live": 988, "live_note": "Live birds (updates the egg ratio)", "placed": "1,000 placed · 12 dead this week"},
    "B": {"den": 600, "spike_min": 4, "counts": [1, 0, 0, 1, 0, 0, 0], "live": 600, "live_note": "Live birds", "placed": "610 placed · 10 dead in total"},
    "C": {"den": 493, "spike_min": 3, "counts": [1, 0, 1, 0, 1, 0, 0], "live": 493, "live_note": "Live birds", "placed": "500 placed · 7 dead in total"},
}


def mortality_panel(code):
    code = clean_batch(code)
    m = MORTALITY[code]
    labels = ["Oct 21", "Oct 22", "Oct 23", "Oct 24", "Oct 25", "Oct 26", "Today"]
    week = []
    for i, n in enumerate(m["counts"]):
        spike = n >= m["spike_min"]
        week.append({
            "label": labels[i], "n": n, "pct": f"{n / m['den'] * 100:.2f}%",
            "bar": round(min(100, n / m["spike_min"] * 100)), "spike": spike, "today": i == 6,
        })
    today = m["counts"][6]
    return {
        "batch": BATCHES[code], "today_n": today, "today_pct": f"{today / m['den'] * 100:.2f}%",
        "live": m["live"], "live_note": m["live_note"], "placed": m["placed"],
        "spike_min": m["spike_min"], "week": week,
    }


def log_deaths(code, n):
    code = clean_batch(code)
    MORTALITY[code]["counts"][6] += n
    MORTALITY[code]["live"] = max(0, MORTALITY[code]["live"] - n)


# ---------------------------------------------------------------- money ----
def money_summary():
    revenue = [
        {"label": "Egg sales", "sub": "650 crates × ₦4,800 (30 eggs a crate)", "amount": 3_120_000},
        {"label": "Culled birds", "sub": "Spent hens sold", "amount": 180_000},
    ]
    expenses = [
        {"label": "Feed", "amount": 1_980_000},
        {"label": "Day-old chicks / pullets", "amount": 450_000},
        {"label": "Labor", "amount": 300_000},
        {"label": "Vaccines and medication", "amount": 210_000},
        {"label": "Utilities", "amount": 95_000},
    ]
    rev_total = sum(r["amount"] for r in revenue)
    exp_total = sum(e["amount"] for e in expenses)
    for e in expenses:
        e["share"] = round(e["amount"] / exp_total * 100)
    return {
        "month": "October 2026",
        "revenue": revenue, "expenses": expenses,
        "revenue_total": rev_total, "expense_total": exp_total,
        "net": rev_total - exp_total, "profit": rev_total >= exp_total,
    }


# ------------------------------------------------------- feed movements ----
# Every change to feed stock is a movement with a direction and a reason.
# Rules used by the design:
# - Adds to stock: purchase, return, count correction (+).
# - Takes out of stock: daily feeding, spoiled, spilled, rodents, sold, transfer, count correction (-).
# - Daily feeding is normally written automatically from the feed log; the
#   other reasons are entered by hand and a note is encouraged.
# - One bag = 25 kg.
# - Feed efficiency: grams of feed per egg = feed used that day / eggs that day.
#   <= 135 g good, 135-145 g watch, > 145 g high. (Layers eat about 110-120 g
#   per bird a day; at 88% production that is roughly 130 g per egg.)
BAG_KG = 25
FEED_TYPES = ["Layers mash", "Grower mash", "Chick mash"]
FEED_REASONS = {
    "in": [("purchase", "Purchased new feed"), ("return", "Returned by supplier"), ("count_up", "Stock count correction (+)")],
    "out": [("fed", "Daily feeding"), ("spoiled", "Spoiled or moldy"), ("spilled", "Spilled or wasted"),
            ("rodents", "Rodent or pest loss"), ("sold", "Sold or given away"), ("transfer", "Moved to another farm"),
            ("count_down", "Stock count correction (-)")],
}
REASON_LABEL = {k: v for rows in FEED_REASONS.values() for k, v in rows}
REASON_DIRECTION = {k: d for d, rows in FEED_REASONS.items() for k, _ in rows}

FEED_MOVEMENTS = [
    {"pk": 9, "date": "Oct 27", "reason": "fed", "feed": "Layers mash", "batch": "Batch A", "kg": 113.6, "note": "", "by": "Worker"},
    {"pk": 8, "date": "Oct 26", "reason": "fed", "feed": "Layers mash", "batch": "Batch A", "kg": 114.6, "note": "", "by": "Worker"},
    {"pk": 7, "date": "Oct 24", "reason": "rodents", "feed": "Grower mash", "batch": "", "kg": 12.5, "note": "Rats chewed 1 bag in the store", "by": "Admin"},
    {"pk": 6, "date": "Oct 22", "reason": "spoiled", "feed": "Layers mash", "batch": "", "kg": 25.0, "note": "Rain got into the store", "by": "Admin"},
    {"pk": 5, "date": "Oct 21", "reason": "sold", "feed": "Chick mash", "batch": "", "kg": 50.0, "note": "Sold 2 bags to a neighbour", "by": "Admin"},
    {"pk": 4, "date": "Oct 20", "reason": "purchase", "feed": "Layers mash", "batch": "", "kg": 1250.0, "note": "50 bags from Agro Feeds, receipt 4471", "by": "Admin"},
    {"pk": 3, "date": "Oct 15", "reason": "count_down", "feed": "Layers mash", "batch": "", "kg": 10.0, "note": "Monthly stock count was short", "by": "Admin"},
    {"pk": 2, "date": "Oct 12", "reason": "return", "feed": "Grower mash", "batch": "", "kg": 25.0, "note": "Supplier took back a torn bag", "by": "Admin"},
    {"pk": 1, "date": "Oct 5", "reason": "purchase", "feed": "Grower mash", "batch": "", "kg": 500.0, "note": "20 bags", "by": "Admin"},
]


def feed_movements(direction="all"):
    """Ledger rows, newest first. direction: 'all', 'in' or 'out'."""
    if direction not in ("all", "in", "out"):
        direction = "all"
    rows = []
    for m in FEED_MOVEMENTS:
        d = REASON_DIRECTION[m["reason"]]
        if direction != "all" and d != direction:
            continue
        rows.append({**m, "direction": d, "is_in": d == "in", "reason_label": REASON_LABEL[m["reason"]],
                     "bags": round(m["kg"] / BAG_KG, 1)})
    added = sum(m["kg"] for m in FEED_MOVEMENTS if REASON_DIRECTION[m["reason"]] == "in")
    removed = sum(m["kg"] for m in FEED_MOVEMENTS if REASON_DIRECTION[m["reason"]] == "out")
    lost = sum(m["kg"] for m in FEED_MOVEMENTS if m["reason"] in ("spoiled", "spilled", "rodents", "count_down"))
    filters = [("all", "All"), ("in", "Added"), ("out", "Removed")]
    return {
        "filter": direction,
        "filters": [{"key": k, "label": l, "active": k == direction} for k, l in filters],
        "rows": rows, "added": added, "removed": removed, "net": added - removed, "lost": lost,
        "month": "October 2026",
    }


def add_movement(reason, feed, batch, kg, note, by="Admin"):
    """Append a movement and adjust the stock card. Returns the row, or None if invalid."""
    if reason not in REASON_LABEL or feed not in FEED_TYPES or kg <= 0:
        return None
    row = {"pk": max(m["pk"] for m in FEED_MOVEMENTS) + 1, "date": "Oct 27", "reason": reason, "feed": feed,
           "batch": BATCHES[batch]["short"] if batch in BATCHES else "", "kg": round(kg, 1), "note": note.strip(), "by": by}
    FEED_MOVEMENTS.insert(0, row)
    for s in FEED_STOCK:
        if s["name"] == feed:
            delta = kg / BAG_KG if REASON_DIRECTION[reason] == "in" else -kg / BAG_KG
            s["bags"] = max(0, round(s["bags"] + delta))
    return row


def feed_efficiency(range_key="7"):
    """Feed used against eggs produced, per day. range_key: '7' or '30'."""
    if range_key not in ("7", "30"):
        range_key = "7"
    n = int(range_key)
    pts = _series()[-n:]
    rows = []
    for p in pts:
        g_bird = 112 + (p["i"] * 5) % 7  # demo: 112-118 g per bird
        feed_kg = LIVE_BIRDS * g_bird / 1000
        eggs = round(p["v"] / 100 * LIVE_BIRDS)
        g_egg = feed_kg * 1000 / eggs
        tone, label = ("success", "Good") if g_egg <= 135 else ("warning", "Watch") if g_egg <= 145 else ("danger", "High")
        rows.append({"label": _lab(p["date"]), "feed_kg": round(feed_kg, 1), "g_bird": g_bird, "eggs": eggs,
                     "pct": p["v"], "g_egg": round(g_egg), "tone": tone, "flag": label})
    tot_feed = sum(r["feed_kg"] for r in rows)
    tot_eggs = sum(r["eggs"] for r in rows)
    g_egg = tot_feed * 1000 / tot_eggs
    worst = max(rows, key=lambda r: r["g_egg"])
    if worst["g_egg"] > 135:
        insight = (f"{worst['label']}: production fell to {worst['pct']}% while the flock still ate {worst['g_bird']} g a bird, "
                   f"so each egg cost {worst['g_egg']} g of feed. Check the flock and the feeders on days like this.")
        insight_tone = "warning"
    else:
        insight = "Feed use is in line with egg output for this period."
        insight_tone = "success"
    return {
        "range": range_key,
        "ranges": [{"key": k, "label": l, "active": k == range_key} for k, l in (("7", "7 days"), ("30", "30 days"))],
        "avg_feed": round(tot_feed / n, 1), "avg_eggs": round(tot_eggs / n), "avg_g_bird": round(sum(r["g_bird"] for r in rows) / n),
        "g_egg": round(g_egg), "kg_crate": round(tot_feed / (tot_eggs / 30), 2),
        "tone": "success" if g_egg <= 135 else "warning" if g_egg <= 145 else "danger",
        "insight": insight, "insight_tone": insight_tone, "rows": list(reversed(rows)),
    }
