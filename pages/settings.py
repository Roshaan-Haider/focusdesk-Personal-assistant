from nicegui import ui

from core.layout import layout
from core.theme import empty_state, page_header


@ui.page("/settings")
def page():
    with layout("Settings", "/settings"):
        page_header("Settings", "Preferences, backups and data")
        empty_state("settings", "Coming soon", "This page is built in a later phase.")
