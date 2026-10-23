from nicegui import ui

from core.layout import layout
from core.theme import empty_state, page_header


@ui.page("/productivity")
def page():
    with layout("Daily Log", "/productivity"):
        page_header("Daily Log", "Track your daily work")
        empty_state("edit_note", "Coming soon", "This page is built in a later phase.")
