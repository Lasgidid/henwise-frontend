# Henwise: layer farm frontend (Django templates + Bootstrap 5 + HTMX)

Frontend handoff for the backend developer. Every page renders today with **sample data** from `core/sample.py`, so you can click through before writing any model. Layers only.

## Run it
```
pip install -r requirements.txt
python manage.py runserver
```
Open http://127.0.0.1:8000/ . The demo "login" only stores a role (worker/admin) in a signed cookie. Money pages are 403 for workers.

## How it is built
- Bootstrap 5.3.3, Bootstrap Icons and HTMX 2.0.4 load from CDN (no SRI hashes; add them or vendor the files for production).
- `static/css/farm.css` holds the theme, `static/js/farm.js` holds the stepper buttons and toasts.
- Pages extend `templates/app_base.html` (sidebar, mobile menu). `active` in the context highlights the nav item.
- HTMX endpoints return **partials** from `templates/partials/`. CSRF is sent on every HTMX request via `hx-headers` on `<body>`.
- A successful POST can send `HX-Trigger: {"toast": {"message": "...", "level": "success|danger|warning"}}` to show a toast. See `_toast()` in `core/views.py`.
- Product name is "Henwise" (working name). Change it in `core/context_processors.py`.

## URLs
| Name | Path | Method | Returns | Context keys |
|---|---|---|---|---|
| home | `/` | GET | page | none |
| waitlist | `/waitlist/` | POST `email` | `_waitlist_result` | ok, email |
| login / admin_login | `/login/`, `/login/admin/` | GET, POST | page / redirect | active_tab. Admin POST also has `code` (6 digits) |
| logout | `/logout/` | GET | redirect | |
| dashboard | `/app/` | GET | page | active, summary, actions, batches |
| next_actions | `/app/next-actions/` | GET (polled every 60 s) | `_next_actions` | actions |
| eggs | `/app/eggs/` | GET | page | active, summary, laying_batches, hold (`{until}` or None) |
| egg_preview | `/app/eggs/preview/` | POST batch, good, cracked, dirty | `_egg_summary` | s. Saves nothing |
| egg_save | `/app/eggs/save/` | POST same fields | `_egg_summary` + toast | s |
| egg_history | `/app/eggs/history/` | GET `?range=7\|30\|all` | page | active, h |
| egg_history_panel | `/app/eggs/history/panel/` | GET `?range=` | `_history_panel` | h |
| batches | `/app/batches/` | GET | page | active, batches |
| batch_create | `/app/batches/new/` | POST name, breed, hatch_date, quantity | `_batch_list` + toast | batches |
| feed | `/app/feed/` | GET | page | active, today, stock, batches |
| feed_log | `/app/feed/log/` | POST batch, kg | `_feed_today` + toast | today, stock, batches |
| feed_stock_add | `/app/feed/stock/` | POST name, bags, expiry | `_feed_stock` + toast | same |
| feed_movements | `/app/feed/movements/` | GET `?type=all\|in\|out` | `_feed_movements` | mv |
| feed_move | `/app/feed/move/` | POST reason, feed, batch (optional), kg, note | `_feed_movements` + out-of-band `#feed-stock` + toast | mv, stock |
| feed_efficiency | `/app/feed/efficiency/` | GET `?range=7\|30` | `_feed_efficiency` | eff |
| vaccines | `/app/health/vaccines/` | GET `?batch=A\|B\|C` | page | active, batches, panel_url, batch, withdrawal, rows |
| vaccine_panel | `/app/health/vaccines/panel/` | GET `?batch=` | `_vaccine_panel` | batch, withdrawal, rows |
| vaccine_given | `/app/health/vaccines/<pk>/given/` | POST | `_vaccine_row` + toast | r |
| mortality | `/app/health/mortality/` | GET `?batch=` | page | active, batches, panel_url + panel keys |
| mortality_panel | `/app/health/mortality/panel/` | GET `?batch=` | `_mortality_panel` | batch, today_n, today_pct, live, live_note, placed, spike_min, week |
| mortality_log | `/app/health/mortality/log/` | POST batch, count | `_mortality_panel` + toast | same |
| money | `/app/money/` | GET (admin) | page | active, m |
| money_summary | `/app/money/summary/` | GET `?month=YYYY-MM` (admin) | `_money_summary` | m |
| money_add | `/app/money/add/` | POST kind, category, amount, date, note (admin) | `_money_summary` + toast | m |

`core/sample.py` shows the exact shape of each dict (`egg_summary`, `history`, `vaccine_panel`, `mortality_panel`, `money_summary`, `NEXT_ACTIONS`, `BATCH_CARDS`). Keep those keys and the templates work unchanged.

## HTMX patterns used
- **Live egg preview**: `#egg-form` posts on `input` (150 ms delay) into `#egg-summary`. The +/- buttons fire `input` too.
- **Batch dropdown (vaccines, mortality)**: `<select>` with `hx-get` on `change`, target `#health-panel`.
- **Range chips**: `hx-get` with `hx-swap="outerHTML"` on `#history-panel`.
- **Mark given**: `hx-post` replaces the row (`#vrow-<pk>`).
- **Next actions**: `hx-trigger="every 60s"`.
- Forms in collapse panels reset and close with `hx-on::after-request`.
- Tip: `django-htmx` gives you `request.htmx` if you want full-page and partial responses from one view.

## Business rules to implement
- Hen-day % = eggs today / live birds x 100. At 85% or more is on target (green), 75 to 85 below target (amber), below 75 a sharp drop (red).
- Layers start laying at about 16 weeks. A batch becomes "Laying" automatically when production reaches 5%.
- Retire at about 18 months (78 weeks). Suggest ordering replacement chicks 16 weeks before retirement.
- Mortality spike alert when deaths in a day exceed 0.5% of live birds. Logging deaths lowers live birds, which feeds the egg ratio.
- A vaccine can have a withdrawal period (days). While active, show the hold and block egg sales for that batch.
- One crate = 30 eggs. Currency is naira.

## Feed movements and feed vs eggs
- Every change to feed stock is one **FeedMovement** row: date, feed type, kg, reason, batch (optional), note, created_by. The reason decides the direction (see `FEED_REASONS` in `core/sample.py`). Adds: purchase, return, count correction (+). Removes: daily feeding, spoiled, spilled, rodents, sold, transfer, count correction (-).
- Stock on hand = sum of additions minus removals per feed type. 1 bag = 25 kg. The old `feed_log` and `feed_stock_add` endpoints can be dropped once `feed_move` is real: daily feeding is just a movement with reason `fed`.
- Feed vs eggs: per day, feed per egg (g) = feed used that day / eggs that day. 135 g or less is good, 135 to 145 watch, above 145 high. The insight line names the worst day. Feed used comes from movements with reason `fed`, eggs from EggCollection.
- `feed_move` returns the ledger and also refreshes the stock card with an HTMX out-of-band swap (`hx-swap-oob` in `_feed_move_response.html`).

## Suggested models
Batch (name, breed, hatch_date, initial_count, status), EggCollection (batch, date, good, cracked, dirty), FeedStock (name, bags, expiry), FeedMovement (feed_type, date, kg, reason, batch nullable, note, created_by), Mortality (batch, date, count), VaccineSchedule (batch, name, due_date, status, given_on, withdrawal_days), Transaction (kind, category, amount, date, note, created_by).

## Replace-the-stubs checklist
1. Real auth (workers and admins, admin 6-digit code), then `role` in `core/context_processors.py` and `admin_required` in `core/views.py`.
2. Models and queries replacing each `sample.*` call.
3. Validation on the POST views (return the form partial with errors, status 422, if you add error display).
4. Real `farm_name` and `today_label`.
5. Production settings: SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASES, static files.
