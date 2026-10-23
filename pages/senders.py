from datetime import date

from nicegui import ui

from core import repository as repo
from core import services
from core.layout import layout
from core.theme import (
    C, confirm, danger_button, empty_state, hex_to_rgba, page_header, primary_button,
    secondary_button, stat_card, toast_error, toast_info, toast_success, usage_color,
)

STATUS_META = {
    "active": ("Active", C["emerald"]),
    "resting": ("Resting", C["amber"]),
    "flagged": ("Flagged", C["danger"]),
}


def progress_bar(used: int, limit: int) -> None:
    pct = min(100, (used / limit * 100) if limit else 0)
    color = usage_color(used, limit)
    with ui.element("div").style(
        "width:100%;height:6px;background:#1F2D4A;border-radius:999px;overflow:hidden"
    ):
        ui.element("div").style(
            f"width:{pct}%;height:100%;background:{color};border-radius:999px;transition:width .3s"
        )


def mini_stat(label: str, value) -> None:
    with ui.column().classes("gap-0"):
        ui.label(str(value)).style("font-weight:700;font-size:14px")
        ui.label(label).classes("fd-sub").style("font-size:11px")


@ui.page("/senders")
def page():
    state = {"search": "", "status": "All"}

    with layout("Sender Accounts", "/senders"):
        actions = page_header("Sender Accounts", "Manage your sending inboxes and daily limits")

        # ------------------------------------------------ dialogs / actions
        def open_dialog(sender: dict | None) -> None:
            s = sender or {}
            with ui.dialog() as dialog, ui.card().style("min-width:480px"):
                ui.label("Edit sender account" if sender else "Add sender account") \
                    .style("font-size:18px;font-weight:600")
                email = ui.input("Email address", value=s.get("email_address", "")) \
                    .props("outlined dense").classes("w-full")
                name = ui.input("Display name (optional)", value=s.get("display_name") or "") \
                    .props("outlined dense").classes("w-full")
                limit = ui.number("Daily limit", value=s.get("daily_limit", 20), min=1, step=1, format="%.0f") \
                    .props("outlined dense").classes("w-full")
                status = ui.select(
                    {"active": "Active", "resting": "Resting", "flagged": "Flagged"},
                    value=s.get("status", "active"), label="Status",
                ).props("outlined dense").classes("w-full")
                reason = ui.input("Reason (why resting / flagged?)", value=s.get("status_reason") or "") \
                    .props("outlined dense type=date stack-label").classes("w-full") \
                    .bind_visibility_from(status, "value", backward=lambda v: v != "active")
                warm = ui.switch("Warm-up mode (5/day, then 10/day, then normal limit)",
                                 value=bool(s.get("warmup_enabled")))
                warm_date = ui.input("Warm-up start date",
                                     value=s.get("warmup_start_date") or date.today().isoformat()) \
                    .props("outlined dense type=date").classes("w-full") \
                    .bind_visibility_from(warm, "value")
                notes = ui.textarea("Notes", value=s.get("notes") or "") \
                    .props("outlined dense rows=2").classes("w-full")

                def save() -> None:
                    ok, msg = services.save_sender(dict(
                        email_address=email.value, display_name=name.value, daily_limit=limit.value,
                        status=status.value, status_reason=reason.value,
                        warmup_enabled=warm.value, warmup_start_date=warm_date.value, notes=notes.value,
                    ), s.get("id"))
                    if ok:
                        toast_success(msg)
                        dialog.close()
                        refresh_all()
                    else:
                        toast_error(msg)

                with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
                    secondary_button("Cancel", on_click=dialog.close)
                    primary_button("Save", on_click=save)
            dialog.open()

        async def delete_flow(s: dict) -> None:
            if repo.sender_has_history(s["id"]):
                with ui.dialog() as d, ui.card().style("min-width:440px"):
                    ui.label("This account can't be deleted").style("font-size:18px;font-weight:600")
                    ui.label(
                        f"{s['email_address']} has outreach history. Deleting it would orphan those "
                        "entries, so you can deactivate it instead. It will disappear from dropdowns "
                        "but all history is kept."
                    ).classes("fd-sub q-my-sm")
                    with ui.row().classes("w-full justify-end gap-2"):
                        secondary_button("Cancel", on_click=lambda: d.submit(False))
                        primary_button("Deactivate instead", on_click=lambda: d.submit(True))
                if await d:
                    repo.set_sender_active(s["id"], False)
                    repo.log_activity("deactivate", "sender", s["id"], f"Deactivated {s['email_address']}")
                    toast_info("Account deactivated.")
                    refresh_all()
            elif await confirm("Delete account?", f"Delete {s['email_address']}? This can't be undone."):
                repo.delete_sender(s["id"])
                repo.log_activity("delete", "sender", s["id"], f"Deleted {s['email_address']}")
                toast_success("Account deleted.")
                refresh_all()

        def toggle_active(s: dict) -> None:
            new_state = not s["is_active"]
            repo.set_sender_active(s["id"], new_state)
            repo.log_activity("update", "sender", s["id"],
                              f"{'Reactivated' if new_state else 'Deactivated'} {s['email_address']}")
            toast_success("Account reactivated." if new_state else "Account deactivated.")
            refresh_all()

        # ------------------------------------------------ refreshable sections
        @ui.refreshable
        def summary() -> None:
            rows = repo.list_senders()
            usable = [r for r in rows if r["is_active"] and r["status"] == "active"]
            at_limit = sum(
                1 for r in usable
                if services.effective_daily_limit(r) > 0
                and r["sent_today"] >= services.effective_daily_limit(r)
            )
            with ui.row().classes("w-full gap-4 no-wrap"):
                stat_card("alternate_email", "Total accounts", len(rows), color=C["info"])
                stat_card("check_circle", "Active accounts", len(usable), color=C["emerald"])
                stat_card("send", "Sent today (all)", sum(r["sent_today"] for r in rows), color=C["purple"])
                stat_card("warning", "At daily limit", at_limit, color=C["amber"])

        def account_card(s: dict) -> None:
            limit = services.effective_daily_limit(s)
            used = s["sent_today"]
            inactive = not s["is_active"]
            label, color = ("Inactive", "#64748B") if inactive else STATUS_META.get(
                s["status"], ("Active", C["emerald"]))
            with ui.element("div").classes("fd-card fd-hover").style(
                "opacity:.6" if inactive else ""
            ):
                with ui.row().classes("w-full items-start justify-between no-wrap"):
                    with ui.column().classes("gap-0"):
                        ui.label(s["email_address"]).style(
                            "font-weight:600;font-size:15px;word-break:break-all")
                        if s["display_name"]:
                            ui.label(s["display_name"]).classes("fd-sub")
                    ui.label(label).classes("fd-pill").style(
                        f"background:{hex_to_rgba(color, .16)};color:{color}")
                if s["status"] != "active" and s["status_reason"]:
                    ui.label(f"Reason: {s['status_reason']}").style(
                        f"color:{C['amber']};font-size:12px;margin-top:6px")
                if s["warmup_enabled"]:
                    ui.label(f"🔥 Warm-up mode · {limit}/day right now").style(
                        f"color:{C['amber']};font-size:12px;margin-top:4px")

                with ui.row().classes("w-full justify-between q-mt-md"):
                    ui.label("Sent today").classes("fd-sub")
                    ui.label(f"{used} / {limit}").style(
                        f"font-weight:700;color:{usage_color(used, limit)}")
                progress_bar(used, limit)

                with ui.row().classes("w-full justify-between q-mt-md"):
                    mini_stat("Last 7 days", s["sent_week"])
                    mini_stat("Total sent", s["total_sent"])
                    mini_stat("Last used", s["last_used"] or "never")

                with ui.row().classes("w-full justify-end gap-1 q-mt-sm"):
                    ui.button(icon="edit", on_click=lambda s=s: open_dialog(s)) \
                        .props("flat round dense color=grey-5").tooltip("Edit")
                    ui.button(icon="play_circle" if inactive else "pause_circle",
                              on_click=lambda s=s: toggle_active(s)) \
                        .props("flat round dense color=grey-5") \
                        .tooltip("Reactivate" if inactive else "Deactivate")
                    ui.button(icon="delete", on_click=lambda s=s: delete_flow(s)) \
                        .props("flat round dense color=red-4").tooltip("Delete")

        @ui.refreshable
        def cards() -> None:
            rows = repo.list_senders(state["search"], state["status"])
            if not rows:
                if not repo.list_senders():
                    empty_state("alternate_email", "No sender accounts yet",
                                "Add the inboxes you send cold emails from.")
                    primary_button("Add your first sender", icon="add",
                                   on_click=lambda: open_dialog(None))
                else:
                    empty_state("search_off", "No accounts match your filters")
                return
            with ui.element("div").style(
                "display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));"
                "gap:16px;width:100%"
            ):
                for s in rows:
                    account_card(s)

        @ui.refreshable
        def dev_tools() -> None:
            with ui.expansion("Developer tools", icon="build").classes("fd-card w-full"):
                ui.label("Insert fake outreach rows (marked TEST) to check the counters.") \
                    .classes("fd-sub q-mb-sm")
                options = {r["id"]: r["email_address"] for r in repo.list_senders()}
                sel = ui.select(options, label="Account").props("outlined dense").style("min-width:300px")

                def add_rows() -> None:
                    if not sel.value:
                        toast_error("Pick an account first.")
                        return
                    repo.insert_test_rows(sel.value, 5)
                    toast_success("Inserted 5 test rows. (Sidebar count updates on next page load.)")
                    refresh_all()

                def clear_rows() -> None:
                    n = repo.delete_test_rows()
                    toast_info(f"Deleted {n} test rows.")
                    refresh_all()

                with ui.row().classes("gap-2 q-mt-sm"):
                    secondary_button("Insert 5 test rows", icon="add", on_click=add_rows)
                    danger_button("Delete test rows", icon="delete", on_click=clear_rows)

        def refresh_all() -> None:
            summary.refresh()
            cards.refresh()
            dev_tools.refresh()

        # ------------------------------------------------ page body
        with actions:
            primary_button("Add Sender Account", icon="add", on_click=lambda: open_dialog(None))

        summary()

        with ui.row().classes("w-full items-center gap-3"):
            search = ui.input(placeholder="Search accounts…").props("dense outlined clearable") \
                .classes("fd-search")
            with search.add_slot("prepend"):
                ui.icon("search").props("size=18px")
            search.on_value_change(lambda e: (state.update(search=e.value or ""), cards.refresh()))
            ui.select(["All", "active", "resting", "flagged", "inactive"], value="All", label="Status") \
                .props("dense outlined").style("min-width:160px") \
                .on_value_change(lambda e: (state.update(status=e.value), cards.refresh()))

        cards()
        dev_tools()