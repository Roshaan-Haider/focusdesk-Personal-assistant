from datetime import date, datetime, timedelta

from nicegui import ui

from core import repository as repo
from core import services
from core.layout import layout, refresh_sidebar_today
from pages._templates_dialog import open_templates_dialog
from core.theme import (
    C, STATUSES, confirm, danger_button, hex_to_rgba, page_header, primary_button,
    secondary_button, section_card, toast_error, toast_info, toast_success, usage_color,
)

LEAD_SOURCES = ["Google Maps", "LinkedIn", "Referral", "Directory", "Other"]
PRIORITIES = ["Low", "Medium", "High"]
NEXT_ACTIONS = ["None", "Follow up", "Send portfolio", "Schedule call", "Wait"]
CURRENCIES = ["USD", "EUR", "GBP", "PKR", "AED", "CAD", "AUD"]


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


@ui.page("/add")
def page(id: int | None = None, duplicate: int | None = None):
    editing = repo.get_outreach(id) if id else None
    source = editing or (repo.get_outreach(duplicate) if duplicate else None)
    editing_id = editing["id"] if editing else None
    f: dict = {}
    state = {"auto_fu": editing is None}

    def val(key, default=""):
        return source.get(key) if source and source.get(key) is not None else default

    def sender_options() -> dict:
        opts = {u["id"]: u["email"] for u in services.usage_summary()}
        if editing and editing["sender_account_id"] not in opts:
            s = repo.get_sender(editing["sender_account_id"])
            if s:
                opts[s["id"]] = s["email_address"]
        return opts

    def initial_sender(opts: dict):
        if editing:
            return editing["sender_account_id"]
        remembered = repo.get_setting("last_selected_sender_id", "")
        try:
            rid = int(remembered)
        except ValueError:
            return None
        return rid if rid in opts else None

    def date_part() -> str:
        return (f["date_sent"].value or now_str())[:10]

    def default_follow_up() -> str:
        days = int(repo.get_setting("default_followup_days", "7") or 7)
        return (date.fromisoformat(date_part()) + timedelta(days=days)).isoformat()

    # ------------------------------------------------------------ refreshables
    @ui.refreshable
    def warnings_panel() -> None:
        for w in services.check_warnings(f["email"].value, f["company"].value, editing_id):
            danger = w["level"] == "danger"
            color = C["danger"] if danger else C["amber"]
            with ui.row().classes("w-full items-center no-wrap gap-2").style(
                f"background:{hex_to_rgba(color, .1)};border:1px solid {hex_to_rgba(color, .35)};"
                "border-radius:8px;padding:8px 12px"
            ):
                ui.icon("block" if danger else "warning").style(f"color:{color}")
                ui.label(w["text"]).classes("col").style("font-size:13px")
                if w.get("id"):
                    ui.button("View entry", on_click=lambda i=w["id"]: ui.navigate.to(f"/add?id={i}")) \
                        .props("flat dense no-caps")

    @ui.refreshable
    def sender_box() -> None:
        sid = f["sender"].value if "sender" in f else None
        with ui.element("div").classes("fd-card").style("padding:10px 16px;min-width:230px"):
            u = services.sender_usage(sid) if sid else None
            if not u:
                ui.label("Sent today").classes("fd-sub")
                ui.label("Select an account").style(f"color:{C['muted']};font-size:13px")
                return
            color = usage_color(u["sent_today"], u["limit"])
            with ui.row().classes("w-full items-baseline justify-between no-wrap"):
                ui.label("Sent today from this account").classes("fd-sub").style("font-size:11px")
                ui.label(f"{u['sent_today']} / {u['limit']}").style(
                    f"font-weight:800;font-size:18px;color:{color}")
            pct = min(100, (u["sent_today"] / u["limit"] * 100) if u["limit"] else 0)
            with ui.element("div").style(
                "width:100%;height:6px;background:#1F2D4A;border-radius:999px;overflow:hidden;margin-top:6px"
            ):
                ui.element("div").style(
                    f"width:{pct}%;height:100%;background:{color};border-radius:999px;transition:width .3s")

    @ui.refreshable
    def limit_banner() -> None:
        sid = f["sender"].value if "sender" in f else None
        u = services.sender_usage(sid) if sid else None
        if not u or not u["limit"] or u["sent_today"] < u["limit"]:
            return
        blocked = repo.get_setting("block_on_limit", "0") == "1"
        with ui.row().classes("w-full items-center no-wrap gap-3").style(
            f"background:{hex_to_rgba(C['danger'], .12)};border:1px solid {hex_to_rgba(C['danger'], .4)};"
            "border-radius:8px;padding:10px 14px"
        ):
            ui.icon("error").style(f"color:{C['danger']}")
            ui.label("Limit reached, switch account" +
                     (". Saving is blocked for this account." if blocked else " (risk of spam flagging).")) \
                .classes("col").style("font-size:13px")
            nxt = services.next_available_sender()
            if nxt and nxt["id"] != sid:
                secondary_button("Switch to next available account",
                                 on_click=lambda: f["sender"].set_value(nxt["id"]))

    @ui.refreshable
    def usage_panel() -> None:
        rows = services.usage_summary()
        with section_card("Sender usage", "Click an account to select it"):
            if not rows:
                ui.label("No active sender accounts yet.").classes("fd-sub")
                ui.button("Manage accounts", on_click=lambda: ui.navigate.to("/senders")) \
                    .props("flat no-caps")
            for u in rows:
                selected = f["sender"].value == u["id"]
                color = usage_color(u["sent_today"], u["limit"])
                row = ui.row().classes("w-full items-center justify-between no-wrap").style(
                    "padding:8px 10px;border-radius:8px;cursor:pointer;transition:background .15s;"
                    + (f"background:{hex_to_rgba(C['emerald'], .12)};" if selected else ""))
                row.on("click", lambda u=u: f["sender"].set_value(u["id"]))
                with row:
                    with ui.row().classes("items-center no-wrap gap-2").style("min-width:0"):
                        ui.element("div").style(
                            f"width:9px;height:9px;border-radius:50%;background:{color};flex-shrink:0")
                        ui.label(u["email"]).style(
                            "font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap")
                    ui.label(f"{u['sent_today']} / {u['limit']}").style(
                        f"font-weight:700;font-size:13px;color:{color}")
            ui.separator().classes("q-my-sm")
            ui.switch("Block saving at limit",
                      value=repo.get_setting("block_on_limit", "0") == "1",
                      on_change=lambda e: repo.set_setting("block_on_limit", "1" if e.value else "0"))

    def refresh_sender_ui() -> None:
        sender_box.refresh()
        limit_banner.refresh()
        usage_panel.refresh()

    # ------------------------------------------------------------ handlers
    def on_sender_change(e) -> None:
        if e.value and not editing:
            repo.set_setting("last_selected_sender_id", e.value)
        refresh_sender_ui()

    def clear_sender() -> None:
        f["sender"].set_value(None)
        repo.set_setting("last_selected_sender_id", "")

    def save_new_sender() -> None:
        email = (f["new_email"].value or "").strip().lower()
        ok, msg = services.save_sender({
            "email_address": email, "daily_limit": f["new_limit"].value, "status": "active"})
        if not ok:
            toast_error(msg)
            return
        s = repo.get_sender_by_email(email)
        f["sender"].set_options(sender_options())
        f["sender"].set_value(s["id"])
        f["new_email"].set_value("")
        f["new_row"].set_visibility(False)
        toast_success("Sender added and selected.")
        refresh_sender_ui()

    def on_template(e) -> None:
        if not e.value:
            return
        t = repo.get_template(e.value)
        if t:
            f["subject"].set_value(services.fill_template(
                t["subject"], f["company"].value, f["contact"].value))
            f["body"].set_value(services.fill_template(
                t["body"], f["company"].value, f["contact"].value))

    def on_date_change(e) -> None:
        if state["auto_fu"]:
            f["follow_up"].set_value(default_follow_up())

    def set_follow_up(days: int) -> None:
        state["auto_fu"] = False
        f["follow_up"].set_value((date.fromisoformat(date_part()) + timedelta(days=days)).isoformat())

    def paste_fill() -> None:
        company, email = services.parse_paste(f["paste"].value)
        if not company and not email:
            toast_error("Couldn't find a company or email in that text.")
            return
        if company:
            f["company"].set_value(company)
        if email:
            f["email"].set_value(email)
        f["paste"].set_value("")

    def collect() -> dict:
        return dict(
            company_name=f["company"].value, recipient_email=f["email"].value,
            sender_account_id=f["sender"].value, date_sent=f["date_sent"].value,
            campaign=f["campaign"].value, template_id=f["template"].value,
            subject=f["subject"].value, email_body=f["body"].value, status=f["status"].value,
            city=f["city"].value, website=f["website"].value, contact_name=f["contact"].value,
            job_title=f["job_title"].value, linkedin_url=f["linkedin"].value,
            lead_source=f["lead_source"].value, priority=f["priority"].value, tags=f["tags"].value,
            next_action=f["next_action"].value, quoted_amount=f["amount"].value,
            currency=f["currency"].value, follow_up_date=f["follow_up"].value, notes=f["notes"].value,
        )

    def reset_form() -> None:
        for key in ("company", "email", "contact", "city", "website", "job_title", "linkedin",
                    "tags", "subject", "body", "notes", "paste"):
            f[key].set_value("")
        for key in ("template", "campaign", "lead_source", "amount"):
            f[key].set_value(None)
        f["status"].set_value("Sent")
        f["priority"].set_value("Medium")
        f["next_action"].set_value("None")
        f["currency"].set_value(repo.get_setting("default_currency", "USD"))
        state["auto_fu"] = True
        f["date_sent"].set_value(now_str())
        f["follow_up"].set_value(default_follow_up())
        warnings_panel.refresh()

    def submit() -> None:
        data = collect()
        if not editing and repo.get_setting("block_on_limit", "0") == "1" and data["sender_account_id"]:
            u = services.sender_usage(data["sender_account_id"])
            if u and u["limit"] and u["sent_today"] >= u["limit"]:
                toast_error("Daily limit reached for this account. Switch account to continue.")
                return
        ok, msg, _ = services.save_outreach(data, editing_id)
        if not ok:
            toast_error(msg)
            return
        toast_success(msg)
        refresh_sidebar_today()
        if editing:
            ui.navigate.to("/outreach")
            return
        reset_form()
        refresh_sender_ui()
        f["company"].run_method("focus")

    # ------------------------------------------------------------ template manager
    def refresh_template_select() -> None:
        f["template"].set_options({t["id"]: t["name"] for t in repo.list_templates("first_touch")})

    def open_templates() -> None:
        open_templates_dialog(on_change=refresh_template_select)

    # ------------------------------------------------------------ page body
    title = "Edit Outreach" if editing else "Add Outreach"
    with layout(title, "/add"):
        actions = page_header(
            title,
            "Update this entry" if editing else "Log a cold email in under 20 seconds",
        )
        with actions:
            secondary_button("Manage templates", icon="description", on_click=open_templates)

        opts = sender_options()

        with ui.row().classes("w-full no-wrap items-start gap-5"):
            # ============ LEFT: form ============
            with ui.column().classes("col gap-4").style("min-width:0"):
                # --- lead ---
                with section_card("Lead", "Who are you emailing?", "w-full"):
                    with ui.row().classes("w-full gap-3 no-wrap"):
                        f["company"] = ui.input("Company name *", value=val("company_name")) \
                            .props("outlined dense debounce=400").classes("col")
                        f["email"] = ui.input("Recipient email *", value=val("recipient_email")) \
                            .props("outlined dense debounce=400").classes("col")
                    f["company"].on_value_change(lambda e: warnings_panel.refresh())
                    f["email"].on_value_change(lambda e: warnings_panel.refresh())
                    with ui.row().classes("w-full gap-2 no-wrap items-center q-mt-sm"):
                        f["paste"] = ui.input(placeholder="Paste-to-fill: Acme Corp, john@acme.com") \
                            .props("outlined dense").classes("col")
                        f["paste"].on("keydown.enter", lambda e: paste_fill())
                        secondary_button("Fill", icon="auto_fix_high", on_click=paste_fill)
                    with ui.column().classes("w-full gap-2 q-mt-sm"):
                        warnings_panel()

                # --- sending ---
                with section_card("Sending", "Account, timing and template", "w-full"):
                    with ui.row().classes("w-full items-start gap-3 no-wrap"):
                        with ui.column().classes("col gap-1"):
                            f["sender"] = ui.select(
                                opts, value=initial_sender(opts), label="Select an account…",
                                on_change=on_sender_change,
                            ).props("outlined dense options-dense").classes("w-full")
                            with ui.row().classes("items-center gap-1"):
                                ui.button("Clear", on_click=clear_sender) \
                                    .props("flat dense no-caps size=sm color=grey-5")
                                ui.button("➕ Add New Sender Email",
                                          on_click=lambda: f["new_row"].set_visibility(not f["new_row"].visible)) \
                                    .props("flat dense no-caps size=sm color=green-5")
                        sender_box()
                    limit_banner()
                    f["new_row"] = ui.row().classes("w-full items-center gap-2 no-wrap q-mt-sm")
                    f["new_row"].set_visibility(False)
                    with f["new_row"]:
                        f["new_email"] = ui.input("New sender email").props("outlined dense").classes("col")
                        f["new_limit"] = ui.number("Daily limit", value=20, min=1, format="%.0f") \
                            .props("outlined dense").style("width:130px")
                        primary_button("Save Email", on_click=save_new_sender)

                    with ui.row().classes("w-full gap-3 no-wrap q-mt-md"):
                        f["date_sent"] = ui.input(
                            "Date & time sent",
                            value=str(val("date_sent", ""))[:16].replace(" ", "T") if editing else now_str(),
                        ).props("outlined dense type=datetime-local stack-label").classes("col")
                        f["status"] = ui.select(STATUSES, value=val("status", "Sent") if editing else "Sent",
                                                label="Status").props("outlined dense").classes("col")
                    f["date_sent"].on_value_change(on_date_change)
                    with ui.row().classes("w-full gap-3 no-wrap"):
                        f["campaign"] = ui.select(repo.list_campaigns(), value=val("campaign", None),
                                                  label="Campaign", clearable=True) \
                            .props("outlined dense").classes("col")
                        f["template"] = ui.select(
                            {t["id"]: t["name"] for t in repo.list_templates("first_touch")},
                            label="Template", clearable=True, on_change=on_template,
                        ).props("outlined dense").classes("col")

                # --- email ---
                with section_card("Email", "Subject and body", "w-full"):
                    f["subject"] = ui.input("Subject", value=val("subject")) \
                        .props("outlined dense").classes("w-full")
                    f["body"] = ui.textarea("Email body", value=val("email_body")) \
                        .props("outlined dense rows=7").classes("w-full")

                # --- more details ---
                with ui.expansion("More details", icon="tune").classes("fd-card w-full"):
                    with ui.column().classes("w-full gap-3 q-pt-sm"):
                        with ui.row().classes("w-full gap-3 no-wrap"):
                            f["city"] = ui.input("City", value=val("city")).props("outlined dense").classes("col")
                            f["website"] = ui.input("Website", value=val("website")).props("outlined dense").classes("col")
                        with ui.row().classes("w-full gap-3 no-wrap"):
                            f["contact"] = ui.input("Contact name", value=val("contact_name")) \
                                .props("outlined dense").classes("col")
                            f["job_title"] = ui.input("Job title", value=val("job_title")) \
                                .props("outlined dense").classes("col")
                        f["linkedin"] = ui.input("LinkedIn URL", value=val("linkedin_url")) \
                            .props("outlined dense").classes("w-full")
                        with ui.row().classes("w-full gap-3 no-wrap"):
                            f["lead_source"] = ui.select(LEAD_SOURCES, value=val("lead_source", None),
                                                         label="Lead source", clearable=True) \
                                .props("outlined dense").classes("col")
                            f["priority"] = ui.select(PRIORITIES, value=val("priority", "Medium"),
                                                      label="Priority").props("outlined dense").classes("col")
                            f["next_action"] = ui.select(NEXT_ACTIONS, value=val("next_action", "None"),
                                                         label="Next action").props("outlined dense").classes("col")
                        f["tags"] = ui.input("Tags (comma separated)", value=val("tags")) \
                            .props("outlined dense").classes("w-full")
                        with ui.row().classes("w-full gap-3 no-wrap"):
                            f["amount"] = ui.number("Quoted amount", value=val("quoted_amount", None),
                                                    min=0, format="%.2f").props("outlined dense").classes("col")
                            f["currency"] = ui.select(
                                CURRENCIES, value=val("currency", repo.get_setting("default_currency", "USD")),
                                label="Currency").props("outlined dense").classes("col")
                        f["follow_up"] = ui.input(
                            "Follow-up date",
                            value=(str(val("follow_up_date", ""))[:10] if editing else default_follow_up()
                                   if "date_sent" in f else ""),
                        ).props("outlined dense type=date stack-label").classes("w-full")
                        f["follow_up"].on("update:model-value", lambda e: state.update(auto_fu=False))
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Quick:").classes("fd-sub")
                            for n in (3, 5, 7, 14):
                                ui.button(f"+{n}d", on_click=lambda n=n: set_follow_up(n)) \
                                    .props("outline dense no-caps size=sm color=green-5")
                        f["notes"] = ui.textarea("Notes (private)", value=val("notes")) \
                            .props("outlined dense rows=3").classes("w-full")

                # --- buttons ---
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Tip: Ctrl+Enter saves").classes("fd-sub")
                    with ui.row().classes("gap-2"):
                        if editing:
                            secondary_button("Cancel", on_click=lambda: ui.navigate.to("/outreach"))
                        else:
                            secondary_button("Clear Form", on_click=reset_form)
                        primary_button("Save Changes" if editing else "Add Outreach",
                                       icon="check", on_click=submit)

            # ============ RIGHT: sender usage ============
            with ui.column().classes("gap-4").style("width:330px;flex-shrink:0"):
                usage_panel()

        def on_key(e) -> None:
            if e.action.keydown and e.key.enter and e.modifiers.ctrl:
                submit()

        ui.keyboard(on_key=on_key, ignore=[])