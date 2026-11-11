"""Stub views.

Every view returns demo data from `core/sample.py` so the templates render.
Replace the data, keep the template names and context variable names (they
are listed in README.md).

HTMX views return a *partial* template, not a full page. Where a POST
succeeds, the response also sets an `HX-Trigger` header that makes the
frontend show a toast (see `_toast`).
"""
import json
from functools import wraps

from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse

from . import sample


def _toast(response, message, level="success"):
    """Ask the browser to show a Bootstrap toast (handled in static/js/farm.js)."""
    response["HX-Trigger"] = json.dumps({"toast": {"message": message, "level": level}})
    return response


def _int(request, key, default=0):
    try:
        return max(0, int(request.POST.get(key, default)))
    except (TypeError, ValueError):
        return default


def admin_required(view):
    # TODO(backend): replace with real permission checks.
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.session.get("role", "admin") != "admin":
            return HttpResponseForbidden("Admins only")
        return view(request, *args, **kwargs)

    return wrapped


# ------------------------------------------------------------- public ----
def home(request):
    return render(request, "marketing/home.html")


def waitlist(request):
    """HTMX POST: email -> small result partial."""
    if request.method != "POST":
        return redirect("home")
    email = request.POST.get("email", "").strip()
    return render(request, "partials/_waitlist_result.html", {"ok": "@" in email, "email": email})


def login_view(request, role="worker"):
    # TODO(backend): authenticate with Django auth; the demo just sets a role.
    if request.method == "POST":
        request.session["role"] = role
        return redirect("dashboard")
    return render(request, "accounts/login.html", {"active_tab": role})


def admin_login(request):
    # TODO(backend): also require the 6-digit verification code (field `code`).
    return login_view(request, role="admin")


def logout_view(request):
    request.session.flush()
    return redirect("home")


# ---------------------------------------------------------- dashboard ----
def dashboard(request):
    return render(request, "dashboard.html", {
        "active": "dashboard",
        "summary": sample.egg_summary(842, 21, 14),
        "actions": sample.NEXT_ACTIONS,
        "batches": sample.BATCH_CARDS,
    })


def next_actions(request):
    """HTMX GET partial, refreshed every 60 seconds on the dashboard."""
    return render(request, "partials/_next_actions.html", {"actions": sample.NEXT_ACTIONS})


# --------------------------------------------------------------- eggs ----
def eggs(request):
    return render(request, "eggs/collect.html", {
        "active": "eggs",
        "summary": sample.egg_summary(842, 21, 14),
        "laying_batches": [sample.BATCHES["A"]],
        "hold": {"until": "Nov 1"},  # None when no withdrawal hold applies
    })


def _egg_summary_from_post(request):
    return sample.egg_summary(_int(request, "good"), _int(request, "cracked"), _int(request, "dirty"))


def egg_preview(request):
    """HTMX POST on every input change: recompute the card, save nothing."""
    return render(request, "partials/_egg_summary.html", {"s": _egg_summary_from_post(request)})


def egg_save(request):
    """HTMX POST: save today's collection, return the same card."""
    response = render(request, "partials/_egg_summary.html", {"s": _egg_summary_from_post(request)})
    return _toast(response, "Today's collection saved (demo: nothing was stored)")


def egg_history(request):
    return render(request, "eggs/history.html", {"active": "eggs", "h": sample.history(request.GET.get("range", "30"))})


def egg_history_panel(request):
    return render(request, "partials/_history_panel.html", {"h": sample.history(request.GET.get("range", "30"))})


# ------------------------------------------------------------ batches ----
def batches(request):
    return render(request, "batches/list.html", {"active": "batches", "batches": sample.BATCH_CARDS})


def batch_create(request):
    """HTMX POST: fields name, breed, hatch_date, quantity."""
    response = render(request, "partials/_batch_list.html", {"batches": sample.BATCH_CARDS})
    return _toast(response, "Batch added (demo: nothing was stored)")


# --------------------------------------------------------------- feed ----
def _feed_ctx():
    return {"today": sample.FEED_TODAY, "stock": sample.FEED_STOCK, "batches": list(sample.BATCHES.values())}


def feed(request):
    return render(request, "feed/index.html", {
        "active": "feed", **_feed_ctx(),
        "mv": sample.feed_movements("all"), "eff": sample.feed_efficiency("7"),
        "reasons": sample.FEED_REASONS, "feed_types": sample.FEED_TYPES,
    })


def feed_log(request):
    """HTMX POST: fields batch, kg."""
    return _toast(render(request, "partials/_feed_today.html", _feed_ctx()), "Feed logged (demo: nothing was stored)")


def feed_stock_add(request):
    """HTMX POST: fields name, bags, expiry."""
    return _toast(render(request, "partials/_feed_stock.html", _feed_ctx()), "Stock added (demo: nothing was stored)")


def feed_movements(request):
    """HTMX GET: ?type=all|in|out -> the movements ledger."""
    return render(request, "partials/_feed_movements.html", {"mv": sample.feed_movements(request.GET.get("type", "all"))})


def feed_move(request):
    """HTMX POST: fields reason, feed, batch (optional), kg, note.

    `reason` decides the direction (see FEED_REASONS in core/sample.py).
    The response is the ledger plus an out-of-band swap that refreshes the stock card.
    """
    try:
        kg = float(request.POST.get("kg", 0))
    except ValueError:
        kg = 0
    row = sample.add_movement(request.POST.get("reason", ""), request.POST.get("feed", ""),
                              request.POST.get("batch", ""), kg, request.POST.get("note", ""))
    response = render(request, "partials/_feed_move_response.html", {"mv": sample.feed_movements("all"), **_feed_ctx()})
    if row is None:
        return _toast(response, "Pick a reason and enter an amount above 0", "warning")
    sign = "Added" if row["reason"] in dict(sample.FEED_REASONS["in"]) else "Removed"
    return _toast(response, f"{sign} {row['kg']} kg: {row['feed']} (demo: nothing was stored)")


def feed_efficiency(request):
    """HTMX GET: ?range=7|30 -> feed used against eggs produced."""
    return render(request, "partials/_feed_efficiency.html", {"eff": sample.feed_efficiency(request.GET.get("range", "7"))})


# ------------------------------------------------------------- health ----
def _health_page_ctx(request):
    return {
        "active": "health",
        "batches": list(sample.BATCHES.values()),
    }


def vaccines(request):
    code = sample.clean_batch(request.GET.get("batch", "A"))
    ctx = {**_health_page_ctx(request), **sample.vaccine_panel(code), "panel_url": reverse("vaccine_panel")}
    return render(request, "health/vaccines.html", ctx)


def vaccine_panel(request):
    """HTMX GET: ?batch=A|B|C -> the panel for that batch."""
    return render(request, "partials/_vaccine_panel.html", sample.vaccine_panel(request.GET.get("batch", "A")))


def vaccine_given(request, pk):
    """HTMX POST: mark one scheduled vaccine as administered, return its row."""
    row = sample.mark_given(pk)
    if row is None:
        raise Http404
    return _toast(render(request, "partials/_vaccine_row.html", {"r": row}), "Marked as given")


def mortality(request):
    code = sample.clean_batch(request.GET.get("batch", "A"))
    ctx = {**_health_page_ctx(request), **sample.mortality_panel(code), "panel_url": reverse("mortality_panel")}
    return render(request, "health/mortality.html", ctx)


def mortality_panel(request):
    return render(request, "partials/_mortality_panel.html", sample.mortality_panel(request.GET.get("batch", "A")))


def mortality_log(request):
    """HTMX POST: fields batch, count. Subtract from live birds, check the spike rule."""
    code = sample.clean_batch(request.POST.get("batch", "A"))
    count = _int(request, "count", 1)
    sample.log_deaths(code, count)
    panel = sample.mortality_panel(code)
    response = render(request, "partials/_mortality_panel.html", panel)
    if panel["today_n"] >= panel["spike_min"]:
        return _toast(response, f"Spike alert: {panel['today_n']} deaths today in {panel['batch']['short']}", "danger")
    return _toast(response, "Deaths logged")


# -------------------------------------------------------------- money ----
@admin_required
def money(request):
    return render(request, "money/index.html", {"active": "money", "m": sample.money_summary()})


@admin_required
def money_summary(request):
    """HTMX GET: ?month=YYYY-MM"""
    return render(request, "partials/_money_summary.html", {"m": sample.money_summary()})


@admin_required
def money_add(request):
    """HTMX POST: fields kind (revenue|expense), category, amount, date, note."""
    return _toast(render(request, "partials/_money_summary.html", {"m": sample.money_summary()}), "Entry added (demo: nothing was stored)")
