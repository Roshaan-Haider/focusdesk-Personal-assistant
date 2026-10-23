from nicegui import ui

from core.layout import layout
from core.theme import empty_state, page_header


@ui.page("/")
def page():
    with layout("Dashboard", "/"):
        page_header("Dashboard", "Your day at a glance")
        empty_state("dashboard", "Coming soon", "This page is built in a later phase.")
