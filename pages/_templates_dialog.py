"""Shared templates manager dialog."""
from nicegui import ui
from core import repository as repo
from core.theme import confirm, primary_button, secondary_button, toast_error, toast_info, toast_success


def edit_template_dialog(t: dict | None, on_saved) -> None:
    t = t or {}
    with ui.dialog() as d, ui.card().style("min-width:580px"):
        ui.label("Edit template" if t else "New template").style("font-size:18px;font-weight:600")
        name = ui.input("Name", value=t.get("name", "")).props("outlined dense").classes("w-full")
        ttype = ui.select({"first_touch": "First touch", "follow_up": "Follow-up"},
                          value=t.get("type", "first_touch"), label="Type") \
            .props("outlined dense").classes("w-full")
        subj = ui.input("Subject", value=t.get("subject") or "").props("outlined dense").classes("w-full")
        body = ui.textarea("Body", value=t.get("body") or "").props("outlined rows=8").classes("w-full")
        ui.label("Placeholders: {company} and {contact}").classes("fd-sub")

        def save() -> None:
            if not (name.value or "").strip():
                toast_error("Template needs a name.")
                return
            repo.save_template(t.get("id"), name.value.strip(), ttype.value, subj.value, body.value)
            toast_success("Template saved.")
            d.close()
            on_saved()

        with ui.row().classes("w-full justify-end gap-2"):
            secondary_button("Cancel", on_click=d.close)
            primary_button("Save", on_click=save)
    d.open()


def open_templates_dialog(on_change=None) -> None:
    with ui.dialog() as dlg, ui.card().style("min-width:600px;max-width:92vw"):
        ui.label("Email templates").style("font-size:18px;font-weight:600")

        @ui.refreshable
        def tpl_list() -> None:
            items = repo.list_templates()
            if not items:
                ui.label("No templates yet.").classes("fd-sub")
            for t in items:
                with ui.row().classes("w-full items-center justify-between no-wrap").style(
                    "padding:8px 4px;border-bottom:1px solid #1F2D4A"
                ):
                    with ui.column().classes("gap-0"):
                        ui.label(t["name"]).style("font-weight:600")
                        ui.label("First touch" if t["type"] == "first_touch" else "Follow-up") \
                            .classes("fd-sub").style("font-size:12px")
                    with ui.row().classes("gap-1"):
                        ui.button(icon="edit", on_click=lambda t=t: edit_template_dialog(t, after)) \
                            .props("flat round dense color=grey-5")
                        ui.button(icon="delete", on_click=lambda t=t: delete_tpl(t)) \
                            .props("flat round dense color=red-4")

        def after() -> None:
            tpl_list.refresh()
            if on_change:
                on_change()

        async def delete_tpl(t: dict) -> None:
            if await confirm("Delete template?", f"Delete '{t['name']}'?"):
                repo.delete_template(t["id"])
                toast_info("Template deleted.")
                after()

        tpl_list()
        with ui.row().classes("w-full justify-between q-mt-sm"):
            primary_button("New template", icon="add", on_click=lambda: edit_template_dialog(None, after))
            secondary_button("Close", on_click=dlg.close)
    dlg.open()
