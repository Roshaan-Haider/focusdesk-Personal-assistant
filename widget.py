"""FocusDesk desktop widget: stopwatch + Darood counter.

Run with:  python widget.py      (or double-click widget.bat)
Only needs tkinter (ships with Python). Shares data/app_data.db with the main app.
"""
import tkinter as tk
from datetime import datetime

try:  # crisp text on high-DPI Windows screens
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:  # noqa: BLE001
    pass

from core import repository as repo
from core.db import init_db

BG, CARD, BORDER, HOVER = "#080D17", "#0F1829", "#1C2940", "#172238"
TEXT, MUTED, FAINT = "#E8EDF5", "#93A1B5", "#64748B"
ACCENT, ACCENT_H, ACCENT_DIM = "#19C7A0", "#3AD9B6", "#10332D"
DANGER, DANGER_H = "#E06464", "#EA7F7F"
FONT, MONO = "Segoe UI", "Consolas"
COUNTER = "Darood"


def clock(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def short(seconds: float) -> str:
    h, m = divmod(int(seconds) // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


class Widget:
    def __init__(self) -> None:
        init_db()
        self.root = tk.Tk()
        self.root.title("FocusDesk")
        self.root.configure(bg=BORDER)
        self.root.overrideredirect(True)          # borderless
        self.root.attributes("-topmost", True)    # always on top
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.active = repo.get_active_session()   # resumes a running session
        self.category = self.active["category"] if self.active else repo.TIME_CATEGORIES[0]
        self.ticks = 0
        self._off = (0, 0)
        self._build()
        self._place()
        self.refresh()
        self._tick()

    def px(self, n: float) -> int:
        return int(n * self.scale)

    # ------------------------------------------------------------ layout
    def _build(self) -> None:
        p = self.px
        body = tk.Frame(self.root, bg=BG)
        body.pack(padx=1, pady=1)
        tk.Frame(body, width=p(290), height=1, bg=BG).pack()   # minimum width

        head = tk.Frame(body, bg=BG, cursor="fleur")
        head.pack(fill="x", padx=p(16), pady=(p(12), p(8)))
        title = tk.Label(head, text="⚡ FocusDesk", font=(FONT, 10, "bold"), fg=TEXT, bg=BG)
        title.pack(side="left")
        close = tk.Label(head, text="✕", font=(FONT, 10), fg=FAINT, bg=BG, cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self.root.destroy())
        close.bind("<Enter>", lambda e: close.config(fg=TEXT))
        close.bind("<Leave>", lambda e: close.config(fg=FAINT))
        for w in (head, title):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag)
            w.bind("<ButtonRelease-1>", self._drag_end)

        chips = tk.Frame(body, bg=BG)
        chips.pack(fill="x", padx=p(16))
        self.chips: dict[str, tk.Label] = {}
        for cat in repo.TIME_CATEGORIES:
            lbl = tk.Label(chips, text=cat, font=(FONT, 9, "bold"),
                           padx=p(9), pady=p(4), cursor="hand2")
            lbl.pack(side="left", padx=(0, p(5)))
            lbl.bind("<Button-1>", lambda e, c=cat: self.select(c))
            self.chips[cat] = lbl

        self.timer = tk.Label(body, text="00:00:00", font=(MONO, 34, "bold"), fg=TEXT, bg=BG)
        self.timer.pack(pady=(p(10), p(6)))
        self.btn = tk.Button(body, text="Start", font=(FONT, 11, "bold"), relief="flat",
                             bd=0, cursor="hand2", pady=p(7), command=self.toggle)
        self.btn.pack(fill="x", padx=p(16))
        self.summary = tk.Label(body, text="", font=(FONT, 9), fg=MUTED, bg=BG,
                                wraplength=p(258), justify="center")
        self.summary.pack(pady=(p(8), p(10)))

        tk.Frame(body, height=1, bg=BORDER).pack(fill="x", padx=p(16))

        box = tk.Frame(body, bg=BG)
        box.pack(fill="x", padx=p(16), pady=p(12))
        left = tk.Frame(box, bg=BG)
        left.pack(side="left")
        tk.Label(left, text=f"{COUNTER} today", font=(FONT, 9), fg=MUTED, bg=BG).pack(anchor="w")
        self.count_lbl = tk.Label(left, text="0", font=(FONT, 28, "bold"), fg=TEXT, bg=BG)
        self.count_lbl.pack(anchor="w")
        self.total_lbl = tk.Label(left, text="", font=(FONT, 8), fg=FAINT, bg=BG)
        self.total_lbl.pack(anchor="w")

        tk.Button(box, text="+", font=(FONT, 20, "bold"), width=3, relief="flat", bd=0,
                  bg=ACCENT, fg="#04130D", activebackground=ACCENT_H,
                  activeforeground="#04130D", cursor="hand2",
                  command=lambda: self.bump(1)).pack(side="right", ipady=p(4))
        tk.Button(box, text="−", font=(FONT, 12), width=2, relief="flat", bd=0,
                  bg=CARD, fg=MUTED, activebackground=HOVER, activeforeground=TEXT,
                  cursor="hand2", command=lambda: self.bump(-1)
                  ).pack(side="right", padx=(0, p(8)), ipady=p(4))

        for key in ("<plus>", "<equal>", "<KP_Add>"):     # keyboard + when focused
            self.root.bind(key, lambda e: self.bump(1))

    def _place(self) -> None:
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        try:
            x = int(repo.get_setting("widget_x", ""))
            y = int(repo.get_setting("widget_y", ""))
        except ValueError:
            x, y = sw - w - 24, 80
        x = min(max(0, x), max(0, sw - w))
        y = min(max(0, y), max(0, sh - h))
        self.root.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------ dragging
    def _drag_start(self, e) -> None:
        self._off = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _drag(self, e) -> None:
        self.root.geometry(f"+{e.x_root - self._off[0]}+{e.y_root - self._off[1]}")

    def _drag_end(self, e) -> None:
        repo.set_setting("widget_x", self.root.winfo_x())
        repo.set_setting("widget_y", self.root.winfo_y())

    # ------------------------------------------------------------ actions
    def select(self, cat: str) -> None:
        if self.active:          # can't switch category mid-session
            return
        self.category = cat
        self.refresh()

    def toggle(self) -> None:
        if self.active:
            repo.stop_session(self.active["id"])
            self.active = None
        else:
            repo.start_session(self.category)
            self.active = repo.get_active_session()
        self.refresh()

    def bump(self, delta: int) -> None:
        repo.counter_add(COUNTER, delta)
        self.refresh_counter()

    # ------------------------------------------------------------ rendering
    def refresh(self) -> None:
        running = self.active is not None
        for cat, lbl in self.chips.items():
            if cat == self.category:
                lbl.config(bg=ACCENT_DIM, fg=ACCENT)
            else:
                lbl.config(bg=CARD, fg=FAINT if running else MUTED)
        if running:
            self.btn.config(text=f"Stop {self.category.lower()}", bg=DANGER, fg="#1A0808",
                            activebackground=DANGER_H, activeforeground="#1A0808")
            self.timer.config(fg=ACCENT)
        else:
            self.btn.config(text=f"Start {self.category.lower()}", bg=ACCENT, fg="#04130D",
                            activebackground=ACCENT_H, activeforeground="#04130D")
            self.timer.config(text="00:00:00", fg=TEXT)
        self.refresh_summary()
        self.refresh_counter()

    def refresh_summary(self) -> None:
        totals = dict(repo.time_totals_today())
        if self.active:
            started = datetime.fromisoformat(self.active["started_at"])
            if started.date() == datetime.now().date():
                totals[self.category] = totals.get(self.category, 0) + \
                    (datetime.now() - started).total_seconds()
        parts = []
        for cat in repo.TIME_CATEGORIES:
            secs = totals.get(cat, 0)
            if secs >= 60 or (self.active and cat == self.category and secs > 0):
                label = "Worked" if cat in repo.WORK_CATEGORIES else cat
                parts.append(f"{label} {short(secs)}")
        self.summary.config(text=("Today: " + "  ·  ".join(parts)) if parts
                            else "Nothing tracked yet today")

    def refresh_counter(self) -> None:
        self.count_lbl.config(text=str(repo.counter_get(COUNTER)))
        self.total_lbl.config(text=f"All time: {repo.counter_total(COUNTER):,}")

    def _tick(self) -> None:
        if self.active:
            started = datetime.fromisoformat(self.active["started_at"])
            self.timer.config(text=clock((datetime.now() - started).total_seconds()))
            self.ticks += 1
            if self.ticks % 40 == 0:       # refresh totals about every 20 seconds
                self.refresh_summary()
        self.root.after(500, self._tick)


if __name__ == "__main__":
    Widget().root.mainloop()