import json
import uuid
from datetime import date, timedelta
from urllib.parse import quote_plus

from nicegui import ui

from core import repository as repo
from core import services
from core.layout import layout
from core.theme import (
    C, STATUSES, STATUS_COLORS, confirm, danger_button, empty_state, hex_to_rgba,
    metric_strip, page_header, primary_button, secondary_button, section, status_badge,
    toast_error, toast_info, toast_success,
)
from pages._templates_dialog import open_templates_dialog

FOLLOWUP_EXCLUDED_STATUSES = ('Replied', 'Interested', 'Meeting Scheduled', 'Won', 'Lost', 'Not Interested')

# In-memory store to preserve filters when returning from /add?id=
_last_outreach_filter_state: dict = {}


@ui.page("/outreach")
def page(q: str = ""):
    with layout("All Outreach", "/outreach"):
        # Header actions
        actions = page_header("All Outreach", "Every cold email you've logged and its follow-up pipeline")

        # ------------------------------------------------ Filter State
        if q:
            init_filters = {"search": q.strip()}
        elif _last_outreach_filter_state:
            init_filters = dict(_last_outreach_filter_state)
        else:
            init_filters = {}

        state = {
            "search": init_filters.get("search", ""),
            "status": init_filters.get("status", "All"),
            "sender_id": init_filters.get("sender_id", "All"),
            "campaign": init_filters.get("campaign", "All"),
            "priority": init_filters.get("priority", "All"),
            "date_from": init_filters.get("date_from", ""),
            "date_to": init_filters.get("date_to", ""),
            "followup_due_only": bool(init_filters.get("followup_due_only", False)),
        }

        # ------------------------------------------------ Metrics Strip
        @ui.refreshable
        def render_metrics():
            m = repo.outreach_metrics()
            fu_color = C["danger"] if m["followups_due"] > 0 else None
            metric_strip([
                ("Total Entries", m["total"]),
                ("Sent This Week", m["sent_this_week"]),
                ("Replies", m["replies"]),
                ("Follow-ups Due", m["followups_due"], None, fu_color),
            ])

        render_metrics()

        # ------------------------------------------------ Detail Drawer (Right Side)
        drawer_data = {"item": None}

        drawer = ui.dialog().props("position=right full-height").classes("fd-drawer")

        @ui.refreshable
        def render_drawer_content():
            item = drawer_data["item"]
            if not item:
                return

            with ui.column().classes("w-full h-full justify-between no-wrap q-pa-md gap-4"):
                # Header
                with ui.column().classes("w-full gap-2"):
                    with ui.row().classes("w-full items-start justify-between no-wrap"):
                        with ui.column().classes("gap-0"):
                            ui.label(item.get("company_name", "")).style("font-size: 20px; font-weight: 700; color: var(--text);")
                            if item.get("city") or item.get("website"):
                                meta_parts = []
                                if item.get("city"):
                                    meta_parts.append(item["city"])
                                if item.get("website"):
                                    meta_parts.append(item["website"])
                                ui.label(" • ".join(meta_parts)).classes("fd-sub").style("font-size: 12px;")
                        ui.button(icon="close", on_click=drawer.close).props("flat round dense size=sm color=grey-5")

                    # Status change row
                    with ui.row().classes("w-full items-center justify-between no-wrap q-py-xs"):
                        status_badge(item.get("status", "Sent"))

                        def on_drawer_status_change(e):
                            new_val = e.value
                            if new_val and new_val != item.get("status"):
                                services.update_status(item["id"], new_val)
                                item["status"] = new_val
                                fetch_data()
                                render_metrics.refresh()
                                toast_success(f"Status changed to {new_val}")

                        ui.select(
                            STATUSES,
                            value=item.get("status", "Sent"),
                            on_change=on_drawer_status_change,
                        ).props("dense outlined options-dense").style("min-width: 170px;")

                    ui.element("div").classes("fd-divider").style("margin: 4px 0 8px;")

                    # Scrollable details
                    with ui.scroll_area().style("height: calc(100vh - 230px); width: 100%;"):
                        with ui.column().classes("w-full gap-3 q-pr-sm"):
                            # Lead details
                            with ui.column().classes("w-full gap-1"):
                                ui.label("LEAD INFO").classes("fd-nav-section").style("padding: 0; font-size: 10px;")
                                with ui.row().classes("w-full justify-between"):
                                    ui.label("Contact:").classes("fd-sub").style("font-size: 12px;")
                                    val = item.get("contact_name") or "—"
                                    if item.get("job_title"):
                                        val += f" ({item['job_title']})"
                                    ui.label(val).style("font-size: 13px; font-weight: 500;")
                                with ui.row().classes("w-full justify-between items-center"):
                                    ui.label("Recipient:").classes("fd-sub").style("font-size: 12px;")
                                    ui.label(item.get("recipient_email", "—")).style("font-size: 13px; font-weight: 500; font-family: monospace;")
                                if item.get("linkedin_url"):
                                    with ui.row().classes("w-full justify-between"):
                                        ui.label("LinkedIn:").classes("fd-sub").style("font-size: 12px;")
                                        ui.link("Profile ↗", item["linkedin_url"], new_tab=True).style("font-size: 12px; color: var(--emerald);")

                            # Outreach details
                            with ui.column().classes("w-full gap-1 q-mt-xs"):
                                ui.label("OUTREACH INFO").classes("fd-nav-section").style("padding: 0; font-size: 10px;")
                                with ui.row().classes("w-full justify-between"):
                                    ui.label("Sender:").classes("fd-sub").style("font-size: 12px;")
                                    ui.label(item.get("sender_email") or "—").style("font-size: 13px;")
                                with ui.row().classes("w-full justify-between"):
                                    ui.label("Date sent:").classes("fd-sub").style("font-size: 12px;")
                                    ui.label(str(item.get("date_sent", ""))[:16]).style("font-size: 13px;")
                                with ui.row().classes("w-full justify-between"):
                                    ui.label("Campaign:").classes("fd-sub").style("font-size: 12px;")
                                    ui.label(item.get("campaign") or "—").style("font-size: 13px;")
                                with ui.row().classes("w-full justify-between"):
                                    ui.label("Priority:").classes("fd-sub").style("font-size: 12px;")
                                    pri = item.get("priority") or "Medium"
                                    p_color = C["danger"] if pri == "High" else C["amber"] if pri == "Medium" else C["muted"]
                                    ui.label(pri).style(f"font-size: 13px; font-weight: 600; color: {p_color};")
                                if item.get("quoted_amount") is not None:
                                    with ui.row().classes("w-full justify-between"):
                                        ui.label("Quoted amount:").classes("fd-sub").style("font-size: 12px;")
                                        ui.label(f"{item.get('currency', 'USD')} {float(item['quoted_amount']):,.0f}").style("font-size: 13px; font-weight: 700;")

                            # Follow-up block
                            with ui.column().classes("w-full gap-1 q-mt-xs q-pa-sm rounded-borders").style("background: var(--elevated); border: 1px solid var(--border);"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    ui.label("FOLLOW-UP").classes("fd-nav-section").style("padding: 0; font-size: 10px;")
                                    if item.get("follow_up_done"):
                                        ui.label("Done ✓").classes("text-emerald font-semibold").style("font-size: 12px;")
                                with ui.row().classes("w-full justify-between items-center"):
                                    ui.label("Date:").classes("fd-sub").style("font-size: 12px;")
                                    ui.label(str(item.get("follow_up_date") or "None")[:10]).style("font-size: 13px; font-weight: 500;")
                                if item.get("follow_up_date") and not item.get("follow_up_done"):
                                    def do_mark_fu():
                                        services.mark_followup_done(item["id"])
                                        item["follow_up_done"] = 1
                                        render_drawer_content.refresh()
                                        fetch_data()
                                        render_metrics.refresh()
                                        toast_success("Marked follow-up as done")

                                    primary_button("Mark follow-up done", icon="check", on_click=do_mark_fu).props("dense size=sm").classes("w-full q-mt-xs")

                            # Subject & Body (with copy buttons)
                            if item.get("subject") or item.get("email_body"):
                                ui.element("div").classes("fd-divider").style("margin: 4px 0;")
                                if item.get("subject"):
                                    with ui.column().classes("w-full gap-1"):
                                        with ui.row().classes("w-full items-center justify-between"):
                                            ui.label("Subject").classes("fd-sub").style("font-size: 11px; font-weight: 600;")
                                            def copy_subject():
                                                js = f'navigator.clipboard.writeText({json.dumps(item.get("subject", ""))})'
                                                ui.run_javascript(js)
                                                toast_info("Subject copied")
                                            ui.button(icon="content_copy", on_click=copy_subject).props("flat round dense size=xs color=grey-5")
                                        ui.label(item["subject"]).classes("q-pa-xs rounded-borders").style("background: var(--elevated); font-size: 12px; width: 100%;")

                                if item.get("email_body"):
                                    with ui.column().classes("w-full gap-1 q-mt-xs"):
                                        with ui.row().classes("w-full items-center justify-between"):
                                            ui.label("Email Body").classes("fd-sub").style("font-size: 11px; font-weight: 600;")
                                            def copy_body():
                                                js = f'navigator.clipboard.writeText({json.dumps(item.get("email_body", ""))})'
                                                ui.run_javascript(js)
                                                toast_info("Body copied")
                                            ui.button(icon="content_copy", on_click=copy_body).props("flat round dense size=xs color=grey-5")
                                        ui.label(item["email_body"]).classes("q-pa-sm rounded-borders").style("background: var(--elevated); font-size: 12px; width: 100%; white-space: pre-wrap; font-family: monospace;")

                            # Notes
                            if item.get("notes"):
                                with ui.column().classes("w-full gap-1 q-mt-xs"):
                                    ui.label("Notes").classes("fd-sub").style("font-size: 11px; font-weight: 600;")
                                    ui.label(item["notes"]).classes("q-pa-xs rounded-borders").style("background: var(--elevated); font-size: 12px; width: 100%;")

                # Drawer bottom actions
                with ui.row().classes("w-full items-center justify-between q-pt-sm no-wrap").style("border-top: 1px solid var(--border);"):
                    secondary_button("Edit", icon="edit", on_click=lambda: ui.navigate.to(f"/add?id={item['id']}"))
                    secondary_button("Duplicate", icon="content_copy", on_click=lambda: ui.navigate.to(f"/add?duplicate={item['id']}"))

                    def do_drawer_delete():
                        iid = item["id"]
                        drawer.close()
                        delete_outreach_rows([iid])

                    danger_button("Delete", icon="delete_outline", on_click=do_drawer_delete)

        with drawer, ui.card().classes("no-shadow no-border q-pa-none").style("background: var(--card); border-left: 1px solid var(--border); width: 440px; max-width: 90vw; height: 100vh; border-radius: 0;"):
            render_drawer_content()

        def open_drawer_for(outreach_id: int):
            full_item = repo.get_outreach(outreach_id)
            if full_item:
                if not full_item.get("sender_email") and full_item.get("sender_account_id"):
                    s = repo.get_sender(full_item["sender_account_id"])
                    if s:
                        full_item["sender_email"] = s["email_address"]
                drawer_data["item"] = full_item
                render_drawer_content.refresh()
                drawer.open()

        # ------------------------------------------------ Trash Dialog
        async def open_trash_dialog():
            with ui.dialog() as trash_dialog, ui.card().style("min-width: 680px; max-width: 900px; max-height: 85vh"):
                @ui.refreshable
                def trash_content():
                    trash_items = repo.list_trash()
                    with ui.row().classes("w-full items-center justify-between no-wrap q-mb-sm"):
                        with ui.column().classes("gap-0"):
                            ui.label("Trash").style("font-size: 18px; font-weight: 700; color: var(--text);")
                            ui.label(f"{len(trash_items)} soft-deleted entries").classes("fd-sub")
                        with ui.row().classes("gap-2 items-center"):
                            if trash_items:
                                async def on_empty():
                                    if await confirm("Empty Trash", "Permanently delete all items in trash? This cannot be undone.", "Empty Trash", danger=True):
                                        cnt = services.empty_trash()
                                        trash_content.refresh()
                                        fetch_data()
                                        render_metrics.refresh()
                                        toast_success(f"Emptied trash ({cnt} items)")
                                danger_button("Empty trash", icon="delete_forever", on_click=on_empty)
                            ui.button(icon="close", on_click=trash_dialog.close).props("flat round dense color=grey-5")

                    ui.element("div").classes("fd-divider")

                    if not trash_items:
                        with ui.column().classes("w-full items-center q-pa-xl gap-2"):
                            ui.icon("delete_outline").props("size=42px").style("color: var(--muted);")
                            ui.label("Trash is empty").style("font-size: 16px; font-weight: 600; color: var(--text);")
                            ui.label("Deleted items will appear here for recovery.").classes("fd-sub")
                    else:
                        with ui.scroll_area().style("height: 400px; width: 100%;"):
                            with ui.column().classes("w-full gap-2 q-pr-sm"):
                                for it in trash_items:
                                    with ui.row().classes("w-full items-center justify-between q-pa-sm rounded-borders").style("background: var(--elevated); border: 1px solid var(--border);"):
                                        with ui.column().classes("gap-0"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.label(it.get("company_name", "")).style("font-weight: 600; color: var(--text);")
                                                if it.get("city"):
                                                    ui.label(f"• {it['city']}").classes("fd-sub").style("font-size: 11px;")
                                            ui.label(f"{it.get('recipient_email', '')} • Deleted: {str(it.get('deleted_at', ''))[:16]}").classes("fd-sub").style("font-size: 11px;")

                                        with ui.row().classes("gap-2 items-center"):
                                            def make_restore_cb(iid=it["id"]):
                                                def do_restore():
                                                    services.restore_outreach(iid)
                                                    trash_content.refresh()
                                                    fetch_data()
                                                    render_metrics.refresh()
                                                    toast_success("Restored entry")
                                                return do_restore

                                            async def make_del_cb(iid=it["id"]):
                                                if await confirm("Delete Permanently", "Permanently delete this entry? This cannot be undone.", "Delete", danger=True):
                                                    services.permanent_delete_outreach(iid)
                                                    trash_content.refresh()
                                                    render_metrics.refresh()
                                                    toast_success("Entry deleted permanently")

                                            secondary_button("Restore", icon="restore", on_click=make_restore_cb())
                                            danger_button("Delete", icon="delete_forever", on_click=lambda iid=it["id"]: make_del_cb(iid))

                trash_content()
                trash_dialog.open()

        # ------------------------------------------------ Do Not Contact Dialog
        async def open_dnc_dialog():
            with ui.dialog() as dnc_dialog, ui.card().style("min-width: 660px; max-width: 820px; max-height: 85vh"):
                dnc_state = {"search": ""}

                with ui.row().classes("w-full items-center justify-between no-wrap q-mb-sm"):
                    with ui.column().classes("gap-0"):
                        ui.label("Do Not Contact (DNC) List").style("font-size: 18px; font-weight: 700; color: var(--text);")
                        ui.label("Companies and emails that should never be emailed").classes("fd-sub")
                    ui.button(icon="close", on_click=dnc_dialog.close).props("flat round dense color=grey-5")

                ui.element("div").classes("fd-divider")

                # Add DNC form
                with ui.column().classes("w-full q-pa-sm rounded-borders gap-2").style("background: var(--elevated); border: 1px solid var(--border);"):
                    ui.label("Add to DNC list").style("font-size: 13px; font-weight: 600; color: var(--text);")
                    with ui.row().classes("w-full gap-2 items-center no-wrap"):
                        dnc_val = ui.input(placeholder="Domain or email (e.g. acme.com or ceo@acme.com)").props("dense outlined").classes("col")
                        dnc_reason = ui.input(placeholder="Reason (optional, e.g. Unsubscribed)").props("dense outlined").classes("col")

                        def on_add_dnc():
                            val = dnc_val.value or ""
                            reason = dnc_reason.value or ""
                            ok, msg = services.add_dnc_entry(val, reason)
                            if ok:
                                dnc_val.value = ""
                                dnc_reason.value = ""
                                dnc_list_view.refresh()
                                toast_success(msg)
                            else:
                                toast_error(msg)

                        primary_button("Add", icon="add", on_click=on_add_dnc).props("dense")

                # Search box for DNC
                with ui.row().classes("w-full items-center justify-between q-mt-sm"):
                    dnc_search = ui.input(placeholder="Search DNC entries…").props("dense outlined clearable").classes("w-full")
                    dnc_search.on("update:model-value", lambda e: (dnc_state.update(search=e.args or ""), dnc_list_view.refresh()))

                @ui.refreshable
                def dnc_list_view():
                    all_entries = repo.list_dnc()
                    search_q = (dnc_state.get("search") or "").strip().lower()
                    if search_q:
                        entries = [e for e in all_entries if search_q in e["value"].lower() or (e.get("reason") and search_q in e["reason"].lower())]
                    else:
                        entries = all_entries

                    if not entries:
                        with ui.column().classes("w-full items-center q-pa-lg gap-1"):
                            ui.label("No DNC entries found").classes("fd-sub")
                        return

                    with ui.scroll_area().style("height: 320px; width: 100%;"):
                        with ui.column().classes("w-full gap-2 q-pr-sm"):
                            for item in entries:
                                with ui.row().classes("w-full items-center justify-between q-pa-sm rounded-borders").style("background: var(--elevated); border: 1px solid var(--border);"):
                                    with ui.column().classes("gap-0"):
                                        ui.label(item["value"]).style("font-weight: 600; font-family: monospace; color: var(--text);")
                                        sub_parts = []
                                        if item.get("reason"):
                                            sub_parts.append(item["reason"])
                                        if item.get("created_at"):
                                            sub_parts.append(f"Added {str(item['created_at'])[:10]}")
                                        if sub_parts:
                                            ui.label(" • ".join(sub_parts)).classes("fd-sub").style("font-size: 11px;")

                                    async def do_remove_dnc(iid=item["id"], ival=item["value"]):
                                        if await confirm("Remove from DNC?", f"Remove '{ival}' from the Do Not Contact list?"):
                                            services.remove_dnc_entry(iid)
                                            dnc_list_view.refresh()
                                            toast_info(f"Removed '{ival}' from DNC")

                                    danger_button("Remove", icon="delete_outline", on_click=lambda iid=item["id"], ival=item["value"]: do_remove_dnc(iid, ival)).props("dense size=sm")

                dnc_list_view()
                dnc_dialog.open()

        # ------------------------------------------------ Export Action
        def do_export(fmt: str):
            filters = {
                "search": state["search"],
                "status": state["status"],
                "sender_id": state["sender_id"],
                "campaign": state["campaign"],
                "priority": state["priority"],
                "date_from": state["date_from"],
                "date_to": state["date_to"],
                "followup_due_only": state["followup_due_only"],
                "include_deleted": False,
            }
            pag = table.pagination or {}
            sort_by = pag.get("sortBy") or "date_sent"
            sort_dir = "desc" if pag.get("descending", True) else "asc"
            try:
                filepath = services.export_outreach(filters, sort_by=sort_by, sort_dir=sort_dir, fmt=fmt)
                ui.download(filepath, filename=filepath.name)
                toast_success(f"Exported {filepath.name} to {filepath.parent}")
            except Exception as e:
                toast_error(f"Export failed: {e}")

        # Wire action buttons in header
        with actions:
            with ui.button("Export", icon="download").props("unelevated no-caps").classes("fd-btn-secondary"):
                with ui.menu().props('anchor="bottom right" self="top right"'):
                    ui.menu_item("CSV (.csv)", on_click=lambda: do_export("csv"))
                    ui.menu_item("Excel (.xlsx)", on_click=lambda: do_export("xlsx"))
            secondary_button("Templates", icon="description", on_click=lambda: open_templates_dialog())
            secondary_button("Do Not Contact", icon="block", on_click=open_dnc_dialog)
            secondary_button("Trash", icon="delete_outline", on_click=open_trash_dialog)
            primary_button("Add Outreach", icon="add", on_click=lambda: ui.navigate.to("/add"))

        # ------------------------------------------------ Saved Filters
        @ui.refreshable
        def render_saved_filters():
            saved = repo.get_saved_filters()
            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                ui.label("Saved filters:").classes("fd-sub").style("font-size: 12px; font-weight: 600;")
                if not saved:
                    ui.label("None yet").classes("fd-sub").style("font-size: 12px;")
                else:
                    for name, fdict in saved.items():
                        def apply_filter(f=fdict):
                            for k, v in f.items():
                                if k in state:
                                    state[k] = v
                            update_filter_inputs()
                            fetch_data()
                            toast_info(f"Loaded filter '{name}'")

                        def remove_filter(n=name):
                            repo.delete_saved_filter(n)
                            render_saved_filters.refresh()
                            toast_info(f"Removed filter '{n}'")

                        with ui.element("div").classes("items-center no-wrap gap-1 q-px-sm q-py-xs rounded-borders").style("background: var(--elevated); border: 1px solid var(--border); display: inline-flex;"):
                            ui.button(name, on_click=apply_filter).props("flat dense no-caps size=sm").style("color: var(--text); padding: 0 4px;")
                            ui.button(icon="close", on_click=remove_filter).props("flat round dense size=xs color=grey-5")

                def save_current_filter():
                    with ui.dialog() as name_dialog, ui.card().style("min-width: 320px"):
                        ui.label("Save current filter").style("font-size: 16px; font-weight: 600; color: var(--text);")
                        name_input = ui.input("Filter name").props("dense outlined autofocus").classes("w-full q-my-sm")

                        def do_save():
                            n = name_input.value.strip()
                            if n:
                                repo.save_saved_filter(n, {
                                    "search": state["search"],
                                    "status": state["status"],
                                    "sender_id": state["sender_id"],
                                    "campaign": state["campaign"],
                                    "priority": state["priority"],
                                    "date_from": state["date_from"],
                                    "date_to": state["date_to"],
                                    "followup_due_only": state["followup_due_only"],
                                })
                                name_dialog.close()
                                render_saved_filters.refresh()
                                toast_success(f"Saved filter '{n}'")

                        with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
                            secondary_button("Cancel", on_click=name_dialog.close)
                            primary_button("Save", on_click=do_save)
                    name_dialog.open()

                ui.button("Save this filter", icon="bookmark_add", on_click=save_current_filter) \
                    .props("flat dense no-caps size=sm").style("color: var(--emerald); font-size: 12px;")

        render_saved_filters()

        # ------------------------------------------------ Filters Row
        senders_dict = {"All": "All Senders"}
        for s in repo.list_senders():
            senders_dict[s["id"]] = s["email_address"]

        campaigns_list = ["All"] + repo.list_campaigns()

        with ui.row().classes("w-full items-center gap-3 flex-wrap"):
            search_input = ui.input(
                placeholder="Search company, recipient, subject, city…",
                value=state["search"],
            ).props("dense outlined clearable debounce=300").classes("grow").style("min-width: 240px;")

            status_select = ui.select(
                ["All"] + STATUSES,
                value=state["status"],
                label="Status",
            ).props("dense outlined options-dense").style("min-width: 130px;")

            sender_select = ui.select(
                senders_dict,
                value=state["sender_id"],
                label="Sender",
            ).props("dense outlined options-dense").style("min-width: 170px;")

            campaign_select = ui.select(
                campaigns_list,
                value=state["campaign"],
                label="Campaign",
            ).props("dense outlined options-dense").style("min-width: 130px;")

            priority_select = ui.select(
                ["All", "High", "Medium", "Low"],
                value=state["priority"],
                label="Priority",
            ).props("dense outlined options-dense").style("min-width: 110px;")

            date_from_input = ui.input(
                "From",
                value=state["date_from"],
            ).props("type=date dense outlined").style("width: 130px;")

            date_to_input = ui.input(
                "To",
                value=state["date_to"],
            ).props("type=date dense outlined").style("width: 130px;")

            fu_due_toggle = ui.checkbox(
                "Follow-up due only",
                value=state["followup_due_only"],
            ).classes("text-sm text-grey-4")

            # Active filter count badge
            @ui.refreshable
            def render_filter_badge():
                cnt = sum([
                    bool(state["search"]),
                    state["status"] != "All",
                    state["sender_id"] != "All",
                    state["campaign"] != "All",
                    state["priority"] != "All",
                    bool(state["date_from"]),
                    bool(state["date_to"]),
                    bool(state["followup_due_only"]),
                ])
                if cnt > 0:
                    with ui.badge(f"{cnt} active", color="teal").props("rounded"):
                        ui.tooltip(f"{cnt} active filter(s)")

            render_filter_badge()

            def clear_all_filters():
                state["search"] = ""
                state["status"] = "All"
                state["sender_id"] = "All"
                state["campaign"] = "All"
                state["priority"] = "All"
                state["date_from"] = ""
                state["date_to"] = ""
                state["followup_due_only"] = False
                _last_outreach_filter_state.clear()
                update_filter_inputs()
                render_filter_badge.refresh()
                fetch_data()

            ui.button("Clear", icon="filter_alt_off", on_click=clear_all_filters) \
                .props("flat dense no-caps size=sm color=grey-5")

        def update_filter_inputs():
            search_input.value = state["search"]
            status_select.value = state["status"]
            sender_select.value = state["sender_id"]
            campaign_select.value = state["campaign"]
            priority_select.value = state["priority"]
            date_from_input.value = state["date_from"]
            date_to_input.value = state["date_to"]
            fu_due_toggle.value = state["followup_due_only"]

        def on_filters_changed():
            state["search"] = (search_input.value or "").strip()
            state["status"] = status_select.value
            state["sender_id"] = sender_select.value
            state["campaign"] = campaign_select.value
            state["priority"] = priority_select.value
            state["date_from"] = date_from_input.value or ""
            state["date_to"] = date_to_input.value or ""
            state["followup_due_only"] = bool(fu_due_toggle.value)
            _last_outreach_filter_state.update(state)
            render_filter_badge.refresh()
            if table.pagination:
                table.pagination["page"] = 1
            fetch_data()

        search_input.on("update:model-value", on_filters_changed)
        status_select.on("update:model-value", on_filters_changed)
        sender_select.on("update:model-value", on_filters_changed)
        campaign_select.on("update:model-value", on_filters_changed)
        priority_select.on("update:model-value", on_filters_changed)
        date_from_input.on("update:model-value", on_filters_changed)
        date_to_input.on("update:model-value", on_filters_changed)
        fu_due_toggle.on("update:model-value", on_filters_changed)

        # ------------------------------------------------ Bulk Actions Bar
        bulk_bar = ui.row().classes("w-full items-center justify-between q-px-md q-py-sm rounded-borders")
        bulk_bar.style("background: var(--elevated); border: 1px solid var(--border);")
        bulk_bar.visible = False

        def on_bulk_delete():
            selected_ids = [r["id"] for r in table.selected]
            if selected_ids:
                delete_outreach_rows(selected_ids)
                table.selected = []
                bulk_bar.visible = False

        with bulk_bar:
            with ui.row().classes("items-center gap-2"):
                ui.icon("check_box").props("size=18px").style("color: var(--emerald);")
                selected_label = ui.label("0 selected").style("font-size: 13px; font-weight: 600; color: var(--text);")
            danger_button("Delete selected", icon="delete_outline", on_click=on_bulk_delete)

        # ------------------------------------------------ Table Columns & Setup
        columns = [
            {"name": "date_sent", "label": "Date", "field": "date_display", "align": "left", "sortable": True},
            {"name": "company_name", "label": "Company", "field": "company_name", "align": "left", "sortable": True},
            {"name": "recipient_email", "label": "Recipient", "field": "recipient_email", "align": "left", "sortable": True},
            {"name": "sender_email", "label": "Sender", "field": "sender_email", "align": "left", "sortable": True},
            {"name": "subject", "label": "Subject", "field": "subject_display", "align": "left", "sortable": True},
            {"name": "quoted_amount", "label": "Quoted", "field": "quoted_display", "align": "right", "sortable": True},
            {"name": "status", "label": "Status", "field": "status", "align": "left", "sortable": True},
            {"name": "follow_up_date", "label": "Follow-up", "field": "followup_display", "align": "left", "sortable": True},
            {"name": "actions", "label": "", "field": "id", "align": "right"},
        ]

        # ------------------------------------------------ Soft Delete with Undo helper
        def delete_outreach_rows(ids_list: list[int]):
            if not ids_list:
                return
            services.soft_delete_outreach(ids_list)
            fetch_data()
            render_metrics.refresh()

            def undo_action():
                services.restore_outreach(ids_list)
                fetch_data()
                render_metrics.refresh()
                toast_success("Restored from trash")

            evt_id = f"undo_{uuid.uuid4().hex}"
            ui.on(evt_id, undo_action)

            msg = "Moved 1 entry to trash" if len(ids_list) == 1 else f"Moved {len(ids_list)} entries to trash"
            ui.notify(
                msg,
                type="info",
                position="bottom-right",
                actions=[{
                    "label": "Undo",
                    "color": "white",
                    ":handler": f"() => emitEvent('{evt_id}')",
                }],
            )

        # ------------------------------------------------ Section & Table
        with section("Emails"):
            empty_container = ui.column().classes("w-full items-center")
            empty_container.visible = False

            table = ui.table(
                rows=[],
                columns=columns,
                row_key="id",
                selection="multiple",
                pagination={
                    "page": 1,
                    "rowsPerPage": 25,
                    "sortBy": "date_sent",
                    "descending": True,
                    "rowsNumber": 0,
                },
            ).classes("w-full")

        # Custom Slots for table
        table.add_slot("body-cell-company_name", """
            <q-td :props="props">
                <div style="font-weight: 600; color: var(--text);">{{ props.row.company_name }}</div>
                <div v-if="props.row.city" style="font-size: 11px; color: var(--muted);">{{ props.row.city }}</div>
            </q-td>
        """)

        table.add_slot("body-cell-subject", """
            <q-td :props="props">
                <div class="ellipsis" style="max-width: 220px; color: var(--text);">
                    {{ props.row.subject_display }}
                    <q-tooltip v-if="props.row.subject" class="bg-dark text-white">{{ props.row.subject }}</q-tooltip>
                </div>
            </q-td>
        """)

        table.add_slot("body-cell-quoted_amount", """
            <q-td :props="props" class="text-right font-mono" style="color: var(--text);">
                {{ props.row.quoted_display }}
            </q-td>
        """)

        table.add_slot("body-cell-status", """
            <q-td :props="props">
                <div class="fd-status">
                    <span class="fd-dot" :style="{ backgroundColor: props.row.status_color }"></span>
                    <span style="color: var(--text);">{{ props.row.status }}</span>
                </div>
            </q-td>
        """)

        table.add_slot("body-cell-follow_up_date", """
            <q-td :props="props">
                <span :class="props.row.followup_class" :style="{ color: props.row.followup_color, fontWeight: props.row.followup_weight }">
                    {{ props.row.followup_display }}
                </span>
            </q-td>
        """)

        table.add_slot("body-cell-actions", """
            <q-td :props="props" class="text-right no-wrap">
                <q-btn flat round dense size="sm" icon="edit" color="grey-5" @click.stop="() => $parent.$emit('edit_row', props.row.id)">
                    <q-tooltip>Edit</q-tooltip>
                </q-btn>
                <q-btn flat round dense size="sm" icon="content_copy" color="grey-5" @click.stop="() => $parent.$emit('duplicate_row', props.row.id)">
                    <q-tooltip>Duplicate</q-tooltip>
                </q-btn>
                <q-btn flat round dense size="sm" icon="delete_outline" color="red-4" @click.stop="() => $parent.$emit('delete_row', props.row.id)">
                    <q-tooltip>Move to trash</q-tooltip>
                </q-btn>
            </q-td>
        """)

        # Table Event Listeners
        table.on("edit_row", lambda e: ui.navigate.to(f"/add?id={e.args}"))
        table.on("duplicate_row", lambda e: ui.navigate.to(f"/add?duplicate={e.args}"))
        table.on("delete_row", lambda e: delete_outreach_rows([e.args]))

        def on_row_clicked(e):
            if len(e.args) > 1 and isinstance(e.args[1], dict) and "id" in e.args[1]:
                open_drawer_for(e.args[1]["id"])

        table.on("rowClick", on_row_clicked)

        def on_selection_change():
            cnt = len(table.selected)
            if cnt > 0:
                selected_label.text = f"{cnt} selected"
                bulk_bar.visible = True
            else:
                bulk_bar.visible = False

        table.on_select(on_selection_change)

        # ------------------------------------------------ Data Fetching & Formatting
        def fetch_data():
            pag = table.pagination or {}
            page_num = pag.get("page", 1)
            rows_per_page = pag.get("rowsPerPage", 25)
            sort_by = pag.get("sortBy") or "date_sent"
            descending = pag.get("descending", True)
            sort_dir = "desc" if descending else "asc"

            filters = {
                "search": state["search"],
                "status": state["status"],
                "sender_id": state["sender_id"],
                "campaign": state["campaign"],
                "priority": state["priority"],
                "date_from": state["date_from"],
                "date_to": state["date_to"],
                "followup_due_only": state["followup_due_only"],
                "include_deleted": False,
            }

            offset = (page_num - 1) * rows_per_page
            db_rows, total = repo.list_outreach(filters, sort_by=sort_by, sort_dir=sort_dir, limit=rows_per_page, offset=offset)

            today_iso = date.today().isoformat()
            formatted = []
            for r in db_rows:
                fu_date = str(r.get("follow_up_date") or "")[:10]
                is_done = bool(r.get("follow_up_done"))
                st = r.get("status")

                if not fu_date:
                    fu_disp = "—"
                    fu_cls = "text-grey-6"
                    fu_color = "var(--muted)"
                    fu_weight = "normal"
                elif is_done:
                    fu_disp = f"{fu_date} ✓"
                    fu_cls = "text-grey-5"
                    fu_color = "var(--muted)"
                    fu_weight = "normal"
                elif st in FOLLOWUP_EXCLUDED_STATUSES:
                    fu_disp = fu_date
                    fu_cls = "text-grey-5"
                    fu_color = "var(--muted)"
                    fu_weight = "normal"
                elif fu_date < today_iso:
                    fu_disp = f"{fu_date} (Overdue)"
                    fu_cls = "text-red-4 font-bold"
                    fu_color = "#EF4444"
                    fu_weight = "700"
                elif fu_date == today_iso:
                    fu_disp = f"{fu_date} (Today)"
                    fu_cls = "text-amber-4 font-bold"
                    fu_color = "#F59E0B"
                    fu_weight = "700"
                else:
                    fu_disp = fu_date
                    fu_cls = "text-grey-4"
                    fu_color = "var(--text)"
                    fu_weight = "normal"

                amt = r.get("quoted_amount")
                curr = r.get("currency") or "USD"
                amt_str = f"{curr} {float(amt):,.0f}" if amt is not None else "—"

                row_dict = dict(r)
                row_dict.update({
                    "date_display": str(r.get("date_sent") or "")[:10],
                    "subject_display": r.get("subject") or "—",
                    "quoted_display": amt_str,
                    "status_color": STATUS_COLORS.get(r.get("status", "Sent"), "#64748B"),
                    "followup_display": fu_disp,
                    "followup_class": fu_cls,
                    "followup_color": fu_color,
                    "followup_weight": fu_weight,
                })
                formatted.append(row_dict)

            table.rows = formatted
            if table.pagination:
                table.pagination["rowsNumber"] = total

            # Check for empty states
            total_db_entries = repo.outreach_metrics()["total"]
            empty_container.clear()
            if total == 0:
                table.visible = False
                empty_container.visible = True
                with empty_container:
                    if total_db_entries == 0:
                        empty_state(
                            "forum",
                            "No outreach logged yet",
                            "Start logging cold emails to track leads, follow-ups, and sending limits.",
                            "Add First Outreach",
                            "/add",
                        )
                    else:
                        empty_state(
                            "search_off",
                            "No matching emails",
                            "No outreach entries match your filter criteria.",
                            "Clear filters",
                            "/outreach",
                        )
            else:
                table.visible = True
                empty_container.visible = False

        table.on_pagination_change(lambda _: fetch_data())

        # Initial fetch
        fetch_data()
