from django.urls import path

from . import views

urlpatterns = [
    # Public
    path("", views.home, name="home"),
    path("waitlist/", views.waitlist, name="waitlist"),  # HTMX POST
    path("login/", views.login_view, name="login"),
    path("login/admin/", views.admin_login, name="admin_login"),
    path("logout/", views.logout_view, name="logout"),
    # App
    path("app/", views.dashboard, name="dashboard"),
    path("app/next-actions/", views.next_actions, name="next_actions"),  # HTMX GET partial
    # Eggs
    path("app/eggs/", views.eggs, name="eggs"),
    path("app/eggs/preview/", views.egg_preview, name="egg_preview"),  # HTMX POST partial
    path("app/eggs/save/", views.egg_save, name="egg_save"),  # HTMX POST partial
    path("app/eggs/history/", views.egg_history, name="egg_history"),
    path("app/eggs/history/panel/", views.egg_history_panel, name="egg_history_panel"),  # HTMX GET partial
    # Layer batches
    path("app/batches/", views.batches, name="batches"),
    path("app/batches/new/", views.batch_create, name="batch_create"),  # HTMX POST partial
    # Feed
    path("app/feed/", views.feed, name="feed"),
    path("app/feed/log/", views.feed_log, name="feed_log"),  # HTMX POST partial
    path("app/feed/stock/", views.feed_stock_add, name="feed_stock_add"),  # HTMX POST partial
    path("app/feed/movements/", views.feed_movements, name="feed_movements"),  # HTMX GET partial
    path("app/feed/move/", views.feed_move, name="feed_move"),  # HTMX POST partial
    path("app/feed/efficiency/", views.feed_efficiency, name="feed_efficiency"),  # HTMX GET partial
    # Health
    path("app/health/vaccines/", views.vaccines, name="vaccines"),
    path("app/health/vaccines/panel/", views.vaccine_panel, name="vaccine_panel"),  # HTMX GET partial
    path("app/health/vaccines/<int:pk>/given/", views.vaccine_given, name="vaccine_given"),  # HTMX POST partial
    path("app/health/mortality/", views.mortality, name="mortality"),
    path("app/health/mortality/panel/", views.mortality_panel, name="mortality_panel"),  # HTMX GET partial
    path("app/health/mortality/log/", views.mortality_log, name="mortality_log"),  # HTMX POST partial
    # Money (admin only)
    path("app/money/", views.money, name="money"),
    path("app/money/summary/", views.money_summary, name="money_summary"),  # HTMX GET partial
    path("app/money/add/", views.money_add, name="money_add"),  # HTMX POST partial
]
