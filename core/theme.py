"""Design system: colors, CSS and reusable UI components."""
from contextlib import contextmanager

from nicegui import ui

C = dict(
    bg="#0B1220", card="#111A2E", elevated="#16223B", border="#1F2D4A",
    text="#E6EDF7", muted="#8A9AB8",
    emerald="#19C7A0", emerald_hover="#3AD9B6",
    teal="#19C7A0", teal_hover="#3AD9B6",
    amber="#F59E0B", danger="#EF4444", info="#3B82F6", purple="#8B5CF6",
)
CHART_COLORS = ["#10B981", "#3B82F6", "#8B5CF6", "#06B6D4", "#F59E0B", "#EC4899"]

STATUSES = [
    "Sent", "Replied", "Interested", "Meeting Scheduled", "Follow-up Sent",
    "Not Interested", "No Response", "Won", "Lost",
]
STATUS_COLORS = {
    "Sent": "#3B82F6", "Replied": "#10B981", "Interested": "#06B6D4",
    "Meeting Scheduled": "#8B5CF6", "Follow-up Sent": "#F59E0B",
    "No Response": "#64748B", "Not Interested": "#EF4444",
    "Lost": "#EF4444", "Won": "#22C55E",
}
PRODUCTIVITY_COLORS = {1: "#EF4444", 2: "#F97316", 3: "#EAB308", 4: "#84CC16", 5: "#22C55E"}


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def usage_color(used: int, limit: int) -> str:
    """Green under 70%, amber 70-99%, red at/over the limit."""
    if limit <= 0:
        return C["emerald"]
    pct = used / limit
    if pct >= 1:
        return C["danger"]
    if pct >= 0.7:
        return C["amber"]
    return C["emerald"]


_VARS = ":root{" + "".join(f"--{k.replace('_','-')}:{v};" for k, v in C.items()) + "}"

_CSS = """
html, body, .q-page, .q-layout { background: var(--bg) !important; color: var(--text); }
body { font-family: 'Inter','Segoe UI',system-ui,-apple-system,sans-serif; }
.nicegui-content { padding: 0 !important; }
* { scrollbar-width: thin; scrollbar-color: #25365A transparent; }
*::-webkit-scrollbar { width: 8px; height: 8px; }
*::-webkit-scrollbar-thumb { background: #25365A; border-radius: 8px; }

.fd-sidebar { background: var(--card) !important; border-right: 1px solid var(--border); }
.fd-topbar { background: rgba(11,18,32,.85) !important; backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border); height: 64px; padding: 0 28px; }
.fd-content { padding: 28px; max-width: 1600px; margin: 0 auto; gap: 20px; }

.fd-logo { font-size: 20px; font-weight: 800; color: var(--text); letter-spacing: -.3px; }
.fd-logo span { color: var(--emerald); }
.fd-logo-sub { font-size: 11px; color: var(--muted); }
.fd-nav-section { font-size: 10px; font-weight: 700; letter-spacing: 1.2px;
  color: #5B6B8C; padding: 14px 14px 6px; }
.fd-nav-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px;
  border-radius: 8px; color: var(--muted); text-decoration: none; font-size: 14px;
  font-weight: 500; transition: all .18s ease; }
.fd-nav-item:hover { background: var(--elevated); color: var(--text); }
.fd-nav-item.active { background: rgba(16,185,129,.12); color: var(--emerald);
  box-shadow: inset 3px 0 0 var(--emerald), 0 0 18px rgba(16,185,129,.12); }
.fd-today { background: var(--elevated); border: 1px solid var(--border);
  border-radius: 12px; padding: 14px; }

.fd-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 20px; box-shadow: 0 4px 18px rgba(0,0,0,.25);
  transition: transform .18s ease, border-color .18s ease; }
.fd-hover:hover { transform: translateY(-2px); border-color: #2A3E66; }
.fd-h1 { font-size: 26px; font-weight: 700; letter-spacing: -.4px; }
.fd-sub { font-size: 14px; color: var(--muted); }
.fd-card-title { font-size: 15px; font-weight: 600; }
.fd-stat-label { font-size: 12px; color: var(--muted); font-weight: 500; }
.fd-stat-value { font-size: 28px; font-weight: 700; letter-spacing: -.5px; line-height: 1.1; }
.fd-stat-icon { width: 38px; height: 38px; border-radius: 10px; display: flex;
  align-items: center; justify-content: center; }
.fd-pill { display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600; }
.fd-fade { animation: fdfade .35s ease both; }
@keyframes fdfade { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

.fd-btn-primary { background: var(--emerald) !important; color: #04130D !important;
  font-weight: 600; border-radius: 8px; transition: all .18s ease; }
.fd-btn-primary:hover { background: var(--emerald-hover) !important;
  box-shadow: 0 0 18px rgba(16,185,129,.35); }
.fd-btn-secondary { background: var(--elevated) !important; color: var(--text) !important;
  border: 1px solid var(--border); border-radius: 8px; }
.fd-btn-danger { background: rgba(239,68,68,.15) !important; color: #F87171 !important;
  border-radius: 8px; }

.q-field--outlined .q-field__control { border-radius: 8px; }
.q-field--outlined .q-field__control:before { border-color: var(--border); }
.q-field--focused .q-field__control:after { border-color: var(--emerald) !important; }
.q-dialog .q-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; }
.q-menu { background: var(--card) !important; border: 1px solid var(--border); border-radius: 10px; }
.fd-search { width: 360px; }

.fd-strip { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 24px; display: flex; align-items: center; gap: 32px; flex-wrap: wrap; }
.fd-metric { display: flex; flex-direction: column; gap: 2px; }
.fd-metric-val { font-size: 22px; font-weight: 700; letter-spacing: -.5px; line-height: 1.1; font-variant-numeric: tabular-nums; }
.fd-metric-lbl { font-size: 12px; color: var(--muted); font-weight: 500; }
.fd-status { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; }
.fd-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.fd-divider { height: 1px; background: var(--border); width: 100%; margin: 6px 0 14px; }

.q-table__container { background: var(--card) !important; color: var(--text) !important; border: 1px solid var(--border); border-radius: 10px; }
.q-table th { font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .5px; color: var(--muted) !important; border-bottom: 1px solid var(--border) !important; }
.q-table td { font-size: 13px; border-bottom: 1px solid var(--border) !important; color: var(--text); }
.q-table tbody tr:hover { background: var(--elevated) !important; }
.q-table__bottom { border-top: 1px solid var(--border) !important; color: var(--muted) !important; font-size: 12px; }
"""


def apply_theme() -> None:
    """Inject the CSS on every page load."""
    ui.add_head_html(f"<style>{_VARS}{_CSS}</style>")


# ---------------- components ----------------
def page_header(title: str, subtitle: str = ""):
    """Title block. Returns a row you can use to add action buttons on the right."""
    with ui.row().classes("w-full items-end justify-between no-wrap fd-fade"):
        with ui.column().classes("gap-0"):
            ui.label(title).classes("fd-h1")
            if subtitle:
                ui.label(subtitle).classes("fd-sub")
        actions = ui.row().classes("gap-2 items-center")
    return actions


@contextmanager
def section_card(title: str | None = None, subtitle: str | None = None, classes: str = ""):
    with ui.element("div").classes(f"fd-card fd-fade {classes}") as card:
        if title:
            with ui.column().classes("gap-0 q-mb-md"):
                ui.label(title).classes("fd-card-title")
                if subtitle:
                    ui.label(subtitle).classes("fd-sub").style("font-size:12px")
        yield card


@contextmanager
def section(title: str, subtitle: str = ""):
    with ui.column().classes("w-full gap-2") as col:
        with ui.row().classes("w-full items-baseline justify-between no-wrap"):
            with ui.column().classes("gap-0"):
                ui.label(title).classes("fd-card-title")
                if subtitle:
                    ui.label(subtitle).classes("fd-sub").style("font-size:12px")
        ui.element("div").classes("fd-divider")
        yield col


def metric_strip(items: list):
    """Compact metric strip. items: list of tuples (label, value, [sub, color]) or dicts."""
    with ui.element("div").classes("fd-strip fd-fade w-full"):
        for i, it in enumerate(items):
            if i > 0:
                ui.element("div").style("width:1px; height:32px; background:var(--border); flex-shrink:0")
            if isinstance(it, dict):
                label = it.get("label", "")
                val = it.get("value", "")
                sub = it.get("sub")
                color = it.get("color")
            else:
                label = it[0]
                val = it[1]
                sub = it[2] if len(it) > 2 else None
                color = it[3] if len(it) > 3 else None

            with ui.column().classes("fd-metric gap-0"):
                v_lbl = ui.label(str(val)).classes("fd-metric-val")
                if color:
                    v_lbl.style(f"color:{color}")
                with ui.row().classes("items-center gap-1 no-wrap"):
                    ui.label(str(label)).classes("fd-metric-lbl")
                    if sub:
                        ui.label(str(sub)).classes("fd-sub").style("font-size:11px")


def progress_bar(used: int, limit: int) -> None:
    pct = min(100, (used / limit * 100) if limit else 0)
    color = usage_color(used, limit)
    with ui.element("div").style(
        "width:100%;height:6px;background:var(--border);border-radius:999px;overflow:hidden"
    ):
        ui.element("div").style(
            f"width:{pct}%;height:100%;background:{color};border-radius:999px;transition:width .3s"
        )


def stat_card(icon: str, label: str, value, delta: float | None = None,
              delta_text: str = "", color: str = C["emerald"], good_when_up: bool = True):
    """KPI card. delta>0 shows green ▲, delta<0 red ▼ (inverted if good_when_up=False)."""
    with ui.element("div").classes("fd-card fd-hover fd-fade").style("flex:1; min-width:200px"):
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            with ui.column().classes("gap-1"):
                ui.label(label).classes("fd-stat-label")
                ui.label(str(value)).classes("fd-stat-value")
            with ui.element("div").classes("fd-stat-icon").style(
                f"background:{hex_to_rgba(color, .15)}; color:{color}"
            ):
                ui.icon(icon).props("size=20px")
        if delta is not None:
            up = delta >= 0
            good = up if good_when_up else not up
            col = C["emerald"] if good else C["danger"]
            arrow = "▲" if up else "▼"
            ui.label(f"{arrow} {abs(delta):g}% {delta_text}").style(
                f"color:{col}; font-size:12px; font-weight:600; margin-top:8px"
            )
        elif delta_text:
            ui.label(delta_text).classes("fd-sub").style("font-size:12px; margin-top:8px")


def status_badge(status: str):
    color = STATUS_COLORS.get(status, "#64748B")
    with ui.row().classes("fd-status items-center no-wrap gap-2") as badge:
        ui.element("span").classes("fd-dot").style(f"background-color:{color}")
        ui.label(status).style("font-size:13px; font-weight:500; color:var(--text)")
    return badge


def primary_button(text: str, icon: str | None = None, on_click=None):
    return ui.button(text, icon=icon, on_click=on_click).props("unelevated no-caps").classes("fd-btn-primary")


def secondary_button(text: str, icon: str | None = None, on_click=None):
    return ui.button(text, icon=icon, on_click=on_click).props("unelevated no-caps").classes("fd-btn-secondary")


def danger_button(text: str, icon: str | None = None, on_click=None):
    return ui.button(text, icon=icon, on_click=on_click).props("unelevated no-caps").classes("fd-btn-danger")


def empty_state(icon: str, title: str, message: str = "",
                cta_label: str | None = None, cta_target: str | None = None):
    with ui.element("div").classes("fd-card w-full fd-fade"):
        with ui.column().classes("w-full items-center q-pa-xl gap-2"):
            with ui.element("div").classes("fd-stat-icon").style(
                f"background:{hex_to_rgba(C['emerald'], .12)}; color:{C['emerald']}; "
                "width:64px; height:64px; border-radius:18px"
            ):
                ui.icon(icon).props("size=32px")
            ui.label(title).style("font-size:18px; font-weight:600")
            if message:
                ui.label(message).classes("fd-sub")
            if cta_label and cta_target:
                primary_button(cta_label, on_click=lambda: ui.navigate.to(cta_target)).classes("q-mt-sm")


async def confirm(title: str, message: str, confirm_label: str = "Delete", danger: bool = True) -> bool:
    """Awaitable confirm dialog: `if await confirm(...): ...`"""
    with ui.dialog() as dialog, ui.card().style("min-width:380px"):
        ui.label(title).style("font-size:18px; font-weight:600")
        ui.label(message).classes("fd-sub q-my-sm")
        with ui.row().classes("w-full justify-end gap-2"):
            secondary_button("Cancel", on_click=lambda: dialog.submit(False))
            btn = danger_button if danger else primary_button
            btn(confirm_label, on_click=lambda: dialog.submit(True))
    return bool(await dialog)


def toast_success(msg: str):
    ui.notify(msg, type="positive", position="bottom-right")


def toast_error(msg: str):
    ui.notify(msg, type="negative", position="bottom-right")


def toast_info(msg: str):
    ui.notify(msg, type="info", position="bottom-right")