"""Shared page shell: sidebar, top bar and content area."""
from contextlib import contextmanager
from urllib.parse import quote_plus

from nicegui import ui
from core import repository as repo, services
from core.theme import apply_theme

NAV = [
    ("OVERVIEW", [("Dashboard", "/", "dashboard")]),
    ("PRODUCTIVITY", [("Daily Log", "/productivity", "edit_note"),
                      ("Calendar", "/calendar", "calendar_month")]),
    ("OUTREACH", [("All Outreach", "/outreach", "forum"),
                  ("Add Outreach", "/add", "add_circle"),
                  ("Follow-ups", "/followups", "notifications_active")]),
    ("ACCOUNTS", [("Sender Accounts", "/senders", "alternate_email")]),
    ("SYSTEM", [("Settings", "/settings", "settings")]),
]


_sidebar_today_refreshers = {}


def refresh_sidebar_today() -> None:
    """Refresh the sidebar Today counter for the current client, if active."""
    try:
        client_id = ui.context.client.id
        refresher = _sidebar_today_refreshers.get(client_id)
        if refresher:
            refresher.refresh()
    except Exception:
        pass


def notification_count() -> int:
    return 0  # wired up in the follow-ups phase


@contextmanager
def layout(title: str, active: str):
    apply_theme()
    ui.dark_mode(True)
    ui.query(".q-layout").props('view="lHh Lpr lFf"')

    # ----- sidebar -----
    with ui.left_drawer(fixed=True).props("width=252 bordered=false").classes("fd-sidebar"):
        with ui.column().classes("w-full h-full no-wrap gap-0"):
            with ui.column().classes("gap-0 q-pa-sm q-mb-sm"):
                ui.html('<div class="fd-logo">⚡ Focus<span>Desk</span></div>')
                ui.label("Personal Productivity & Outreach Workspace").classes("fd-logo-sub")
            for section, items in NAV:
                ui.label(section).classes("fd-nav-section")
                for label, path, icon in items:
                    cls = "fd-nav-item active" if path == active else "fd-nav-item"
                    with ui.link(target=path).classes(cls):
                        ui.icon(icon).props("size=20px")
                        ui.label(label)
            ui.space()

            @ui.refreshable
            def render_today():
                with ui.column().classes("fd-today w-full gap-1"):
                    ui.label("TODAY").classes("fd-nav-section").style("padding:0 0 4px")
                    with ui.row().classes("w-full justify-between"):
                        ui.label("Emails sent").classes("fd-sub")
                        ui.label(str(repo.sent_today_total())).style("font-weight:700")
                    with ui.row().classes("w-full justify-between"):
                        ui.label("Hours logged").classes("fd-sub")
                        ui.label(f"{repo.hours_today():g}h").style("font-weight:700")

            render_today()
            try:
                cid = ui.context.client.id
                _sidebar_today_refreshers[cid] = render_today
                ui.context.client.on_disconnect(lambda: _sidebar_today_refreshers.pop(cid, None))
            except Exception:
                pass

    # ----- top bar -----
    with ui.header(elevated=False).classes("fd-topbar items-center justify-between no-wrap"):
        ui.label(title).style("font-size:16px; font-weight:600")
        with ui.row().classes("items-center gap-3 no-wrap"):
            search = ui.input(placeholder="Search companies, emails, subjects…") \
                .props("dense outlined rounded").classes("fd-search")
            with search.add_slot("prepend"):
                ui.icon("search").props("size=18px")

            def handle_top_search():
                val = (search.value or "").strip()
                if val:
                    ui.navigate.to(f"/outreach?q={quote_plus(val)}")
                else:
                    ui.navigate.to("/outreach")

            search.on("keydown.enter", handle_top_search)

            alerts = services.limit_alerts()
            count = len(alerts)
            with ui.button(icon="notifications").props("flat round dense color=grey-5"):
                if count:
                    ui.badge(str(count), color="red").props("floating")
                with ui.menu().props('anchor="bottom right" self="top right"'):
                    with ui.column().classes("q-pa-md gap-2").style("min-width:300px"):
                        ui.label("Notifications").style("font-weight:600")
                        if not alerts:
                            ui.label("You're all caught up.").classes("fd-sub")
                        for a in alerts:
                            with ui.row().classes("items-center no-wrap gap-2"):
                                ui.icon("warning").style("color:#F59E0B")
                                ui.label(a).style("font-size:13px")

    # ----- content -----
    with ui.column().classes("fd-content w-full"):
        yield