from nicegui import ui

from core.layout import layout
from core.theme import empty_state, page_header


@ui.page("/calendar")
def page():
    with layout("Calendar", "/calendar"):
        page_header("Calendar", "Everything by date")
        empty_state("calendar_month", "Coming soon", "This page is built in a later phase.")
