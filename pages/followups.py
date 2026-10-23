from nicegui import ui

from core.layout import layout
from core.theme import empty_state, page_header


@ui.page("/followups")
def page():
    with layout("Follow-ups", "/followups"):
        page_header("Follow-ups", "Never miss a follow-up")
        empty_state("notifications_active", "Coming soon", "This page is built in a later phase.")
