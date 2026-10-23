import logging

from nicegui import ui

from core.db import BASE_DIR, init_db

(BASE_DIR / "logs").mkdir(exist_ok=True)
logging.basicConfig(
    filename=BASE_DIR / "logs" / "app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

init_db()

# Importing each page registers its route.
import pages.dashboard        # noqa: E402,F401
import pages.productivity     # noqa: E402,F401
import pages.calendar_page    # noqa: E402,F401
import pages.outreach         # noqa: E402,F401
import pages.add_outreach     # noqa: E402,F401
import pages.followups        # noqa: E402,F401
import pages.senders          # noqa: E402,F401
import pages.settings         # noqa: E402,F401

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="FocusDesk", dark=True, reload=False, port=8080, favicon="⚡")