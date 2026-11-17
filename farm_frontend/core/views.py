"""Django views for Henwise.

Operational records are stored through the models. HTMX endpoints continue
to return the partial templates expected by the frontend.
"""
import json
from functools import wraps

from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from datetime import date, timedelta
from .models import Batch, EggCollection, FeedMovement, Mortality, VaccineSchedule, Transaction, WaitlistEntry

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
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("admin_login")
        if not request.user.is_staff:
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
    ok = False
    if email:
        _, created = WaitlistEntry.objects.get_or_create(email=email)
        ok = True
    return render(request, "partials/_waitlist_result.html", {"ok": ok, "email": email})


def login_view(request, role="worker"):
    if request.method == "POST":
        username = request.POST.get("username") or request.POST.get("email")
        if "@" in username:
            from django.contrib.auth import get_user_model
            user_record = get_user_model().objects.filter(email__iexact=username).first()
            username = user_record.get_username() if user_record else username
        user = authenticate(request, username=username, password=request.POST.get("password"))
        code=request.POST.get("code", "")
        code_configured=getattr(settings,"ADMIN_LOGIN_CODE","")
        if user and (role != "admin" or (user.is_staff and len(code_configured)==6 and code.isdigit() and code==code_configured)):
            login(request, user)
            return redirect("dashboard")
        return render(request, "accounts/login.html", {"active_tab": role, "error": "Sign-in details could not be verified."}, status=401)
    return render(request, "accounts/login.html", {"active_tab": role})


def admin_login(request):
    # TODO(backend): also require the 6-digit verification code (field `code`).
    return login_view(request, role="admin")


def logout_view(request):
    logout(request)
    return redirect("home")


# ---------------------------------------------------------- dashboard ----
@login_required
def dashboard(request):
    batches = _batch_cards()
    today = timezone.localdate()
    eggs = EggCollection.objects.filter(date=today).aggregate(g=Sum("good"),c=Sum("cracked"),d=Sum("dirty"))
    live = sum(b.live_count for b in Batch.objects.filter(active=True))
    summary = sample.egg_summary(eggs["g"] or 0, eggs["c"] or 0, eggs["d"] or 0, birds=live)
    return render(request, "dashboard.html", {
        "active": "dashboard",
        "summary": summary,
        "actions": _actions(),
        "batches": batches,
    })


@login_required
def next_actions(request):
    """HTMX GET partial, refreshed every 60 seconds on the dashboard."""
    return render(request, "partials/_next_actions.html", {"actions": _actions()})


def _actions():
    today=timezone.localdate(); actions=[]
    for v in VaccineSchedule.objects.select_related("batch").filter(given_on__isnull=True,due_date__lte=today+timedelta(days=7)).order_by("due_date")[:5]:
        overdue=v.due_date<today
        actions.append({"tone":"danger" if overdue else "warning","icon":"exclamation-triangle-fill" if overdue else "eyedropper","title":f"Give {v.name}","detail":v.batch.name,"pill":"Overdue" if overdue else ("Today" if v.due_date==today else v.due_date.strftime("%b %d")),"url_name":"vaccines"})
    return actions


# --------------------------------------------------------------- eggs ----
@login_required
def eggs(request):
    laying = Batch.objects.filter(active=True, hatch_date__lte=timezone.localdate()-timedelta(weeks=16))
    batches = [{"code":b.pk,"name":b.name,"sub":f"{b.live_count} live birds"} for b in laying]
    totals=EggCollection.objects.filter(batch__in=laying,date=timezone.localdate()).aggregate(g=Sum("good"),c=Sum("cracked"),d=Sum("dirty"))
    live=sum(b.live_count for b in laying)
    hold=None
    active_hold=VaccineSchedule.objects.filter(batch__in=laying,given_on__isnull=False,withdrawal_days__gt=0).order_by("-given_on").first()
    if active_hold and active_hold.given_on + timedelta(days=active_hold.withdrawal_days)>timezone.localdate(): hold={"until":(active_hold.given_on+timedelta(days=active_hold.withdrawal_days)).strftime("%b %d")}
    return render(request, "eggs/collect.html", {
        "active": "eggs",
        "summary": sample.egg_summary(totals["g"] or 0, totals["c"] or 0, totals["d"] or 0,birds=live),
        "laying_batches": batches,
        "hold": hold,
    })


def _egg_summary_from_post(request):
    batch=Batch.objects.filter(pk=request.POST.get("batch")).first()
    return sample.egg_summary(_int(request, "good"), _int(request, "cracked"), _int(request, "dirty"),birds=batch.live_count if batch else 0)


@login_required
def egg_preview(request):
    """HTMX POST on every input change: recompute the card, save nothing."""
    return render(request, "partials/_egg_summary.html", {"s": _egg_summary_from_post(request)})


@login_required
def egg_save(request):
    """HTMX POST: save today's collection, return the same card."""
    batch = Batch.objects.filter(pk=request.POST.get("batch"), active=True).first()
    if not batch:
        return _toast(render(request, "partials/_egg_summary.html", {"s": _egg_summary_from_post(request)}), "Choose a valid batch", "warning")
    EggCollection.objects.create(batch=batch, date=timezone.localdate(), good=_int(request,"good"), cracked=_int(request,"cracked"), dirty=_int(request,"dirty"), created_by=request.user if request.user.is_authenticated else None)
    return _toast(render(request, "partials/_egg_summary.html", {"s": _egg_summary_from_post(request)}), "Today's collection saved")


@login_required
def egg_history(request):
    return render(request, "eggs/history.html", {"active": "eggs", "h": _egg_history(request.GET.get("range", "30"))})


@login_required
def egg_history_panel(request):
    return render(request, "partials/_history_panel.html", {"h": _egg_history(request.GET.get("range", "30"))})


def _egg_history(range_key):
    key=range_key if range_key in ("7","30","all") else "30"
    qs=EggCollection.objects.select_related("batch").order_by("date")
    if key!="all": qs=qs.filter(date__gte=timezone.localdate()-timedelta(days=int(key)-1))
    daily={}
    for row in qs:
        val=daily.setdefault(row.date,{"eggs":0,"birds":0})
        val["eggs"]+=row.good+row.cracked+row.dirty; val["birds"]+=row.batch.live_count
    points=[]
    for d,v in daily.items():
        pct=v["eggs"]/v["birds"]*100 if v["birds"] else 0
        points.append({"date":d,"v":pct})
    if not points:
        return {"range":key,"ranges":[{"key":k,"label":l,"active":key==k} for k,l in (("7","7 days"),("30","30 days"),("all","All time"))],"bars":[],"x_labels":[],"y_labels":["100","90","80","70","60"],"target_pos":50,"avg":0,"best":{"v":0,"label":"—"},"on_target":0,"days":0,"eggs":0,"crates":0,"range_label":"No collections yet","weeks":[]}
    points.sort(key=lambda x:x["date"])
    avg=sum(p["v"] for p in points)/len(points); best=max(points,key=lambda p:p["v"])
    bars=[{"label":p["date"].strftime("%b %d"),"v":round(p["v"],1),"h":round(min(100,max(2,p["v"])),1),"dip":p["v"]<82,"below":p["v"]<85} for p in points]
    return {"range":key,"ranges":[{"key":k,"label":l,"active":key==k} for k,l in (("7","7 days"),("30","30 days"),("all","All time"))],"bars":bars,"x_labels":[bars[round(i*(len(bars)-1)/4)]["label"] for i in range(5)],"y_labels":["100","75","50","25","0"] if key=="all" else ["100","90","80","70","60"],"target_pos":25 if key=="all" else 50,"avg":round(avg,1),"best":{"v":round(best["v"],1),"label":best["date"].strftime("%b %d")},"on_target":sum(p["v"]>=85 for p in points),"days":len(points),"eggs":sum(v["eggs"] for v in daily.values()),"crates":sum(v["eggs"] for v in daily.values())//30,"range_label":f"{points[0]['date']:%b %d} – {points[-1]['date']:%b %d, %Y}","weeks":[]}


# ------------------------------------------------------------ batches ----
@login_required
def batches(request):
    cards = _batch_cards()
    return render(request, "batches/list.html", {"active": "batches", "batches": cards})


@login_required
def batch_create(request):
    """HTMX POST: fields name, breed, hatch_date, quantity."""
    try:
        Batch.objects.create(name=request.POST["name"].strip(), breed=request.POST.get("breed", "").strip(), hatch_date=date.fromisoformat(request.POST["hatch_date"]), initial_count=max(1,int(request.POST["quantity"])))
    except (KeyError, ValueError):
        return _toast(render(request, "partials/_batch_list.html", {"batches": _batch_cards()}), "Enter valid batch details", "warning")
    return _toast(render(request, "partials/_batch_list.html", {"batches": _batch_cards()}), "Batch added")


def _batch_cards():
    cards=[]
    for b in Batch.objects.filter(active=True).order_by("hatch_date"):
        age=max(0,(timezone.localdate()-b.hatch_date).days//7)
        cards.append({"code":b.pk,"name":b.name,"stage":"Laying" if age>=16 else "Rearing","stage_tone":"success" if age>=16 else "warning","sub":f"{b.live_count} birds · week {age} · hatched {b.hatch_date:%b} {b.hatch_date.day}","big":f"{max(0,78-age)} wks","big_label":"of life left","marker":min(100,age/78*100),"chips":[],"next":"","url_name":"eggs"})
    return cards


# --------------------------------------------------------------- feed ----
def _feed_ctx():
    today=timezone.localdate(); movements=FeedMovement.objects.select_related("batch").filter(date=today,reason="fed")
    feed_today=[]
    for m in movements:
        birds=m.batch.live_count if m.batch else 0
        grams=round(float(m.kg)*1000/birds) if birds else 0
        feed_today.append({"batch":f"{m.batch.name} · {m.feed_type}" if m.batch else m.feed_type,"detail":f"{m.kg} kg · {birds} birds","g":grams,"tone":"success" if 110<=grams<=120 else "neutral","note":""})
    stock=[]
    for feed_name in sample.FEED_TYPES:
        ins=sum(float(m.kg) for m in FeedMovement.objects.filter(feed_type=feed_name,reason__in=("purchase","return","count_up")))
        outs=sum(float(m.kg) for m in FeedMovement.objects.filter(feed_type=feed_name).exclude(reason__in=("purchase","return","count_up")))
        stock.append({"name":feed_name,"bags":max(0,round((ins-outs)/25,1)),"expires":"—","days_left":None,"pct":0,"tone":"neutral","flag":""})
    batches=[{"code":b.pk,"name":b.name,"short":b.name,"sub":f"{b.live_count} birds"} for b in Batch.objects.filter(active=True)]
    return {"today":feed_today,"stock":stock,"batches":batches}


@login_required
def feed(request):
    return render(request, "feed/index.html", {
        "active": "feed", **_feed_ctx(),
        "mv": _movement_context("all"), "eff": _feed_efficiency("7"),
        "reasons": sample.FEED_REASONS, "feed_types": sample.FEED_TYPES,
    })


@login_required
def feed_log(request):
    """HTMX POST: fields batch, kg."""
    batch=Batch.objects.filter(pk=request.POST.get("batch"),active=True).first()
    try: kg=float(request.POST.get("kg",0))
    except (TypeError,ValueError): kg=0
    if not batch or kg<=0: return _toast(render(request,"partials/_feed_today.html",_feed_ctx()),"Choose a batch and enter a positive amount","warning")
    FeedMovement.objects.create(batch=batch,feed_type=request.POST.get("feed_type") or "Feed",reason="fed",kg=kg,created_by=request.user)
    return _toast(render(request, "partials/_feed_today.html", _feed_ctx()), "Feed logged")


@login_required
def feed_stock_add(request):
    """HTMX POST: fields name, bags, expiry."""
    try: bags=float(request.POST.get("bags",0)); feed_name=request.POST.get("name","").strip()
    except (TypeError,ValueError): bags=0; feed_name=""
    if bags<=0 or not feed_name: return _toast(render(request,"partials/_feed_stock.html",_feed_ctx()),"Enter a feed type and positive bag count","warning")
    FeedMovement.objects.create(feed_type=feed_name,reason="purchase",kg=bags*25,note="Stock received",created_by=request.user)
    return _toast(render(request, "partials/_feed_stock.html", _feed_ctx()), "Stock added")


@login_required
def feed_movements(request):
    """HTMX GET: ?type=all|in|out -> the movements ledger."""
    return render(request, "partials/_feed_movements.html", {"mv": _movement_context(request.GET.get("type", "all"))})


@login_required
def feed_move(request):
    """HTMX POST: fields reason, feed, batch (optional), kg, note.

    `reason` decides the direction (see FEED_REASONS in core/sample.py).
    The response is the ledger plus an out-of-band swap that refreshes the stock card.
    """
    try:
        kg = float(request.POST.get("kg", 0))
    except ValueError:
        kg = 0
    reason, feed = request.POST.get("reason", ""), request.POST.get("feed", "")
    allowed = {k for groups in sample.FEED_REASONS.values() for k, _ in groups}
    batch = Batch.objects.filter(pk=request.POST.get("batch")).first() if request.POST.get("batch") else None
    if reason not in allowed or feed not in sample.FEED_TYPES or kg <= 0:
        row = None
    else:
        row = FeedMovement.objects.create(reason=reason, feed_type=feed, batch=batch, kg=kg, note=request.POST.get("note", "").strip(), created_by=request.user if request.user.is_authenticated else None)
    ctx = {"mv": _movement_context(request.GET.get("type", "all")), **_feed_ctx()}
    response = render(request, "partials/_feed_move_response.html", ctx)
    if row is None:
        return _toast(response, "Pick a reason and enter an amount above 0", "warning")
    sign = "Added" if row.is_in else "Removed"
    return _toast(response, f"{sign} {row.kg} kg: {row.feed_type}")


def _movement_context(direction="all"):
    direction = direction if direction in ("all","in","out") else "all"
    qs=FeedMovement.objects.select_related("batch","created_by").order_by("-date","-pk")
    rows=[]; added=removed=lost=0
    for m in qs:
        d="in" if m.is_in else "out"
        if d=="in": added+=float(m.kg)
        else: removed+=float(m.kg)
        if m.reason in ("spoiled","spilled","rodents","count_down"): lost+=float(m.kg)
        if direction!="all" and direction!=d: continue
        rows.append({"pk":m.pk,"date":f"{m.date:%b} {m.date.day}","reason":m.reason,"feed":m.feed_type,"batch":m.batch.name if m.batch else "","kg":float(m.kg),"note":m.note,"by":m.created_by.username if m.created_by else "—","direction":d,"is_in":d=="in","reason_label":sample.REASON_LABEL.get(m.reason,m.reason),"bags":round(float(m.kg)/25,1)})
    filters=[("all","All"),("in","Added"),("out","Removed")]
    return {"filter":direction,"filters":[{"key":k,"label":l,"active":k==direction} for k,l in filters],"rows":rows,"added":added,"removed":removed,"net":added-removed,"lost":lost,"month":timezone.localdate().strftime("%B %Y")}


@login_required
def feed_efficiency(request):
    """HTMX GET: ?range=7|30 -> feed used against eggs produced."""
    return render(request, "partials/_feed_efficiency.html", {"eff": _feed_efficiency(request.GET.get("range", "7"))})


def _feed_efficiency(range_key="7"):
    key=range_key if range_key in ("7","30") else "7"; n=int(key); today=timezone.localdate(); rows=[]
    for offset in range(n-1,-1,-1):
        day=today-timedelta(days=offset)
        feed=float(FeedMovement.objects.filter(date=day,reason="fed").aggregate(v=Sum("kg"))["v"] or 0)
        egg=EggCollection.objects.filter(date=day).aggregate(v=Sum("good"))["v"] or 0
        birds=sum(b.live_count for b in Batch.objects.filter(active=True))
        gbird=round(feed*1000/birds) if birds else 0; g_egg=round(feed*1000/egg) if egg else 0
        tone,label=("success","Good") if g_egg<=135 else ("warning","Watch") if g_egg<=145 else ("danger","High")
        rows.append({"label":day.strftime("%b %d"),"feed_kg":round(feed,1),"g_bird":gbird,"eggs":egg,"pct":round(egg/max(1,birds)*100,1),"g_egg":g_egg,"tone":tone,"flag":label})
    total_feed=sum(r["feed_kg"] for r in rows); total_eggs=sum(r["eggs"] for r in rows); avg_g=round(total_feed*1000/total_eggs) if total_eggs else 0
    return {"range":key,"ranges":[{"key":k,"label":l,"active":key==k} for k,l in (("7","7 days"),("30","30 days"))],"avg_feed":round(total_feed/n,1),"avg_eggs":round(total_eggs/n),"avg_g_bird":round(sum(r["g_bird"] for r in rows)/n),"g_egg":avg_g,"kg_crate":round(total_feed/(total_eggs/30),2) if total_eggs else 0,"tone":"success" if avg_g<=135 else "warning" if avg_g<=145 else "danger","insight":"Feed and egg data for the selected period." if total_eggs else "No feed and egg records for this period yet.","insight_tone":"neutral","rows":list(reversed(rows))}


# ------------------------------------------------------------- health ----
def _health_page_ctx(request):
    return {
        "active": "health",
        "batches": [{"code":b.pk,"name":b.name,"short":b.name,"sub":f"{b.live_count} birds","age":f"Week {max(0,(timezone.localdate()-b.hatch_date).days//7)}"} for b in Batch.objects.filter(active=True)],
    }


@login_required
def vaccines(request):
    batch=Batch.objects.filter(pk=request.GET.get("batch")).first() or Batch.objects.filter(active=True).first()
    panel=_vaccine_context(batch)
    ctx = {**_health_page_ctx(request), **panel, "panel_url": reverse("vaccine_panel")}
    return render(request, "health/vaccines.html", ctx)


@login_required
def vaccine_panel(request):
    """HTMX GET: ?batch=A|B|C -> the panel for that batch."""
    batch=Batch.objects.filter(pk=request.GET.get("batch")).first()
    return render(request, "partials/_vaccine_panel.html", _vaccine_context(batch))


def _vaccine_context(batch):
    if not batch: return {"batch":{"code":"","name":"No batches","short":"No batch"},"withdrawal":{"tone":"success","big":"None active","progress":None,"text":"Add a batch to begin tracking vaccines."},"rows":[]}
    today=timezone.localdate(); rows=[]
    for v in batch.vaccines.order_by("-due_date"):
        given=bool(v.given_on); overdue=not given and v.due_date<today
        rows.append({"pk":v.pk,"kind":"done" if given else "overdue" if overdue else "pending","name":v.name,"sub":f"Given {v.given_on:%b %d}" if given else f"Due {v.due_date:%b %d, %Y}"})
    hold=batch.vaccines.filter(given_on__isnull=False,withdrawal_days__gt=0).order_by("-given_on").first()
    end=hold.given_on+timedelta(days=hold.withdrawal_days) if hold else None
    active=end and end>today
    withdrawal={"tone":"warning" if active else "success","big":f"{(end-today).days} days left" if active else "None active","progress":None,"text":f"{hold.name} given {hold.given_on:%b %d}; hold ends {end:%b %d}." if active else "No active egg withdrawal hold."}
    return {"batch":{"code":batch.pk,"name":batch.name,"short":batch.name},"withdrawal":withdrawal,"rows":rows}


@login_required
def vaccine_given(request, pk):
    """HTMX POST: mark one scheduled vaccine as administered, return its row."""
    v=VaccineSchedule.objects.filter(pk=pk).first()
    if not v:
        raise Http404
    v.given_on=timezone.localdate(); v.save(update_fields=["given_on"])
    row={"pk":v.pk,"kind":"done","name":v.name,"sub":f"Given {v.given_on:%b %d}"}
    return _toast(render(request, "partials/_vaccine_row.html", {"r": row}), "Marked as given")


@login_required
def mortality(request):
    batch=Batch.objects.filter(pk=request.GET.get("batch")).first() or Batch.objects.filter(active=True).first()
    ctx = {**_health_page_ctx(request), **(_mortality_context(batch) if batch else _empty_mortality()), "panel_url": reverse("mortality_panel")}
    return render(request, "health/mortality.html", ctx)


@login_required
def mortality_panel(request):
    batch=Batch.objects.filter(pk=request.GET.get("batch")).first()
    return render(request, "partials/_mortality_panel.html", _mortality_context(batch) if batch else _empty_mortality())


def _empty_mortality():
    return {"batch":{"code":"","name":"No batches","short":"No batch"},"today_n":0,"today_pct":"0.00%","live":0,"live_note":"Live birds","placed":"Add a batch to start tracking","spike_min":1,"week":[]}


@login_required
def mortality_log(request):
    """HTMX POST: fields batch, count. Subtract from live birds, check the spike rule."""
    count = _int(request, "count", 1)
    batch = Batch.objects.filter(pk=request.POST.get("batch")).first()
    if not batch or count < 1:
        return _toast(render(request, "partials/_mortality_panel.html", _empty_mortality()), "Enter a valid batch and count", "warning")
    Mortality.objects.create(batch=batch, count=count, date=timezone.localdate(), created_by=request.user if request.user.is_authenticated else None)
    panel = _mortality_context(batch)
    response = render(request, "partials/_mortality_panel.html", panel)
    if panel["today_n"] > panel["spike_min"]:
        return _toast(response, f"Spike alert: {panel['today_n']} deaths today in {panel['batch']['short']}", "danger")
    return _toast(response, "Deaths logged")


def _mortality_context(batch):
    today=timezone.localdate(); den=batch.live_count
    week=[]
    for i in range(6,-1,-1):
        d=today-timedelta(days=i); n=batch.mortalities.filter(date=d).aggregate(n=Sum("count"))["n"] or 0
        spike=max(1,int(den*.005)+1); week.append({"label":"Today" if i==0 else d.strftime("%b %d"),"n":n,"pct":f"{n/max(1,den)*100:.2f}%","bar":round(min(100,n/spike*100)),"spike":n>den*.005,"today":i==0})
    n=week[-1]["n"]
    return {"batch":{"code":batch.pk,"name":batch.name,"short":batch.name},"today_n":n,"today_pct":week[-1]["pct"],"live":den,"live_note":"Live birds","placed":f"{batch.initial_count} placed","spike_min":max(1,int(den*.005)+1),"week":week}


# -------------------------------------------------------------- money ----
@admin_required
def money(request):
    return render(request, "money/index.html", {"active": "money", "m": _money_context()})


@admin_required
def money_summary(request):
    """HTMX GET: ?month=YYYY-MM"""
    return render(request, "partials/_money_summary.html", {"m": _money_context(request.GET.get("month"))})


@admin_required
def money_add(request):
    """HTMX POST: fields kind (revenue|expense), category, amount, date, note."""
    try:
        amount=float(request.POST.get("amount",0)); day=date.fromisoformat(request.POST.get("date", "")); kind=request.POST.get("kind")
        if kind not in ("revenue","expense") or amount<=0: raise ValueError
        Transaction.objects.create(kind=kind,category=request.POST.get("category","").strip(),amount=amount,date=day,note=request.POST.get("note","").strip(),created_by=request.user)
    except (ValueError, TypeError):
        return _toast(render(request, "partials/_money_summary.html", {"m": _money_context(request.POST.get("date", "")[:7])}), "Enter a valid amount and date", "warning")
    return _toast(render(request, "partials/_money_summary.html", {"m": _money_context(request.POST.get("date", "")[:7])}), "Entry added")


def _money_context(month_key=None):
    try: year, month = map(int, (month_key or timezone.localdate().strftime("%Y-%m")).split("-"))
    except (ValueError, TypeError): year,month=timezone.localdate().year,timezone.localdate().month
    entries=Transaction.objects.filter(date__year=year,date__month=month)
    def groups(kind):
        data=[]
        for row in entries.filter(kind=kind).values("category").annotate(amount=Sum("amount")).order_by("category"):
            data.append({"label":row["category"],"sub":"","amount":row["amount"]})
        return data
    revenue,expenses=groups("revenue"),groups("expense")
    rt=sum((r["amount"] for r in revenue),0); et=sum((r["amount"] for r in expenses),0)
    for e in expenses: e["share"]=round(e["amount"]/et*100) if et else 0
    return {"month":date(year,month,1).strftime("%B %Y"),"revenue":revenue,"expenses":expenses,"revenue_total":rt,"expense_total":et,"net":rt-et,"profit":rt>=et}
