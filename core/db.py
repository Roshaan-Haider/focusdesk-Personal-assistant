"""Database setup: connection helper, schema, defaults and seed data."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app_data.db"
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS sender_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_address TEXT UNIQUE NOT NULL,
    display_name TEXT,
    daily_limit INTEGER DEFAULT 20,
    status TEXT DEFAULT 'active',
    status_reason TEXT,
    warmup_enabled INTEGER DEFAULT 0,
    warmup_start_date DATE,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_outreach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_sent DATETIME NOT NULL,
    company_name TEXT NOT NULL,
    city TEXT, website TEXT, contact_name TEXT, job_title TEXT, linkedin_url TEXT,
    recipient_email TEXT NOT NULL,
    recipient_domain TEXT,
    sender_account_id INTEGER NOT NULL REFERENCES sender_accounts(id),
    subject TEXT, email_body TEXT, campaign TEXT,
    template_id INTEGER, lead_source TEXT,
    priority TEXT DEFAULT 'Medium',
    tags TEXT,
    status TEXT DEFAULT 'Sent',
    followup_number INTEGER DEFAULT 0,
    next_action TEXT,
    quoted_amount REAL, final_amount REAL,
    currency TEXT DEFAULT 'USD',
    follow_up_date DATE,
    follow_up_done INTEGER DEFAULT 0,
    reply_date DATE, reply_summary TEXT, notes TEXT,
    deleted_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_productivity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date DATE UNIQUE NOT NULL,
    app_used TEXT, work_done TEXT, details TEXT,
    productivity_score INTEGER CHECK (productivity_score BETWEEN 1 AND 5),
    blockers TEXT,
    hours_worked REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    subject TEXT, body TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS do_not_contact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    value TEXT UNIQUE NOT NULL,
    reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT, entity TEXT, entity_id INTEGER, description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS time_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    duration_seconds INTEGER DEFAULT 0,
    note TEXT
);

CREATE TABLE IF NOT EXISTS counter_log (
    log_date DATE NOT NULL,
    counter_name TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (log_date, counter_name)
);

CREATE INDEX IF NOT EXISTS idx_sessions_start ON time_sessions(started_at);

CREATE INDEX IF NOT EXISTS idx_outreach_date ON email_outreach(date_sent);
CREATE INDEX IF NOT EXISTS idx_outreach_sender ON email_outreach(sender_account_id);
CREATE INDEX IF NOT EXISTS idx_outreach_followup ON email_outreach(follow_up_date);
CREATE INDEX IF NOT EXISTS idx_outreach_domain ON email_outreach(recipient_domain);
CREATE INDEX IF NOT EXISTS idx_productivity_date ON daily_productivity(log_date);
"""

DEFAULT_SETTINGS = {
    "default_followup_days": "7",
    "daily_goal": "30",
    "block_on_limit": "0",
    "user_name": "",
    "default_currency": "USD",
    "last_selected_sender_id": "",
    "theme": "dark",
    "last_backup_date": "",
    "onboarding_done": "0",
    "max_followups": "3",
    "domain_cooldown_days": "14",
}

DEFAULT_CAMPAIGNS = [
    "General Outreach", "Website Development", "AI Automation", "Android Development",
]

DEFAULT_TEMPLATES = [
    ("Intro: general", "first_touch",
     "Quick idea for {company}",
     "Hi {contact},\n\nI came across {company} and had an idea that could help. "
     "Would you be open to a quick chat?\n\nBest regards"),
    ("Follow-up: gentle nudge", "follow_up",
     "Re: Quick idea for {company}",
     "Hi {contact},\n\nJust following up on my previous email. "
     "Happy to share more details if useful.\n\nBest regards"),
]


@contextmanager
def db():
    """Yield a connection; commit on success, roll back on error."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create folders, tables, default settings and seed data (idempotent)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for folder in ("backups", "exports", "logs", "assets"):
        (BASE_DIR / folder).mkdir(exist_ok=True)

    with db() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
        for name in DEFAULT_CAMPAIGNS:
            conn.execute("INSERT OR IGNORE INTO campaigns (name) VALUES (?)", (name,))
        if conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO templates (name, type, subject, body) VALUES (?, ?, ?, ?)",
                DEFAULT_TEMPLATES,
            )