from datetime import date, timedelta

from core.db import db


# ---------- settings ----------
def get_setting(key: str, default: str = "") -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row and row["value"] is not None else default


def set_setting(key: str, value) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
# ---------- activity log ----------
def log_activity(action: str, entity: str, entity_id: int | None, description: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO activity_log (action, entity, entity_id, description) VALUES (?,?,?,?)",
            (action, entity, entity_id, description),
        )


# ---------- sidebar "Today" widget ----------
def sent_today_total() -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM email_outreach "
            "WHERE date(date_sent)=? AND deleted_at IS NULL",
            (date.today().isoformat(),),
        ).fetchone()
    return row["c"]


def hours_today() -> float:
    with db() as conn:
        row = conn.execute(
            "SELECT COALESCE(hours_worked, 0) AS h FROM daily_productivity WHERE log_date=?",
            (date.today().isoformat(),),
        ).fetchone()
    return float(row["h"]) if row else 0.0

# ---------- sender accounts ----------
def list_senders(search: str = "", status: str = "All") -> list[dict]:
    """All senders with live stats: sent today, last 7 days, total, last used."""
    today = date.today()
    week_start = today - timedelta(days=6)
    base = (
        "SELECT s.*, "
        "(SELECT COUNT(*) FROM email_outreach e WHERE e.sender_account_id=s.id "
        "  AND e.deleted_at IS NULL AND date(e.date_sent)=?) AS sent_today, "
        "(SELECT COUNT(*) FROM email_outreach e WHERE e.sender_account_id=s.id "
        "  AND e.deleted_at IS NULL AND date(e.date_sent)>=?) AS sent_week, "
        "(SELECT COUNT(*) FROM email_outreach e WHERE e.sender_account_id=s.id "
        "  AND e.deleted_at IS NULL) AS total_sent, "
        "(SELECT MAX(date(e.date_sent)) FROM email_outreach e WHERE e.sender_account_id=s.id "
        "  AND e.deleted_at IS NULL) AS last_used "
        "FROM sender_accounts s"
    )
    params: list = [today.isoformat(), week_start.isoformat()]
    where = []
    if search:
        where.append("(s.email_address LIKE ? OR s.display_name LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    if status == "inactive":
        where.append("s.is_active=0")
    elif status in ("active", "resting", "flagged"):
        where.append("s.status=? AND s.is_active=1")
        params.append(status)
    if where:
        base += " WHERE " + " AND ".join(where)
    base += " ORDER BY s.email_address"
    with db() as conn:
        return [dict(r) for r in conn.execute(base, params).fetchall()]


def get_sender(sender_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM sender_accounts WHERE id=?", (sender_id,)).fetchone()
    return dict(row) if row else None


def create_sender(d: dict) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO sender_accounts (email_address, display_name, daily_limit, status, "
            "status_reason, warmup_enabled, warmup_start_date, notes) VALUES (?,?,?,?,?,?,?,?)",
            (d["email_address"], d["display_name"], d["daily_limit"], d["status"],
             d["status_reason"], d["warmup_enabled"], d["warmup_start_date"], d["notes"]),
        )
        return cur.lastrowid


def update_sender(sender_id: int, d: dict) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE sender_accounts SET email_address=?, display_name=?, daily_limit=?, status=?, "
            "status_reason=?, warmup_enabled=?, warmup_start_date=?, notes=? WHERE id=?",
            (d["email_address"], d["display_name"], d["daily_limit"], d["status"],
             d["status_reason"], d["warmup_enabled"], d["warmup_start_date"], d["notes"], sender_id),
        )


def set_sender_active(sender_id: int, active: bool) -> None:
    with db() as conn:
        conn.execute("UPDATE sender_accounts SET is_active=? WHERE id=?", (1 if active else 0, sender_id))


def sender_has_history(sender_id: int) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM email_outreach WHERE sender_account_id=?", (sender_id,)
        ).fetchone()
    return row["c"] > 0


def delete_sender(sender_id: int) -> None:
    with db() as conn:
        conn.execute("DELETE FROM sender_accounts WHERE id=?", (sender_id,))


def count_sent_today(sender_id: int) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM email_outreach WHERE sender_account_id=? "
            "AND date(date_sent)=? AND deleted_at IS NULL",
            (sender_id, date.today().isoformat()),
        ).fetchone()
    return row["c"]


# ---------- developer test rows ----------
def insert_test_rows(sender_id: int, n: int = 5) -> None:
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db() as conn:
        for i in range(n):
            conn.execute(
                "INSERT INTO email_outreach (date_sent, company_name, recipient_email, "
                "recipient_domain, sender_account_id, subject, status, notes) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (now, f"Test Company {i + 1}", f"test{i + 1}@example.com", "example.com",
                 sender_id, "Test subject", "Sent", "TEST"),
            )


def delete_test_rows() -> int:
    with db() as conn:
        cur = conn.execute("DELETE FROM email_outreach WHERE notes='TEST'")
        return cur.rowcount


# ---------- campaigns / templates ----------
def list_campaigns() -> list[str]:
    with db() as conn:
        return [r["name"] for r in conn.execute("SELECT name FROM campaigns ORDER BY name").fetchall()]


def list_templates(ttype: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM templates", []
    if ttype:
        sql += " WHERE type=?"
        params.append(ttype)
    sql += " ORDER BY name"
    with db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_template(template_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM templates WHERE id=?", (template_id,)).fetchone()
    return dict(row) if row else None


def save_template(template_id, name: str, ttype: str, subject: str, body: str) -> None:
    with db() as conn:
        if template_id:
            conn.execute("UPDATE templates SET name=?, type=?, subject=?, body=? WHERE id=?",
                         (name, ttype, subject, body, template_id))
        else:
            conn.execute("INSERT INTO templates (name, type, subject, body) VALUES (?,?,?,?)",
                         (name, ttype, subject, body))


def delete_template(template_id: int) -> None:
    with db() as conn:
        conn.execute("DELETE FROM templates WHERE id=?", (template_id,))


# ---------- do not contact ----------
def find_dnc(email: str, domain: str) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM do_not_contact WHERE lower(value) IN (?, ?) LIMIT 1",
            (email.lower(), domain.lower()),
        ).fetchone()
    return dict(row) if row else None


# ---------- outreach ----------
OUTREACH_FIELDS = [
    "date_sent", "company_name", "city", "website", "contact_name", "job_title", "linkedin_url",
    "recipient_email", "recipient_domain", "sender_account_id", "subject", "email_body",
    "campaign", "template_id", "lead_source", "priority", "tags", "status", "followup_number",
    "next_action", "quoted_amount", "final_amount", "currency", "follow_up_date",
    "follow_up_done", "reply_date", "reply_summary", "notes",
]


def get_outreach(outreach_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM email_outreach WHERE id=?", (outreach_id,)).fetchone()
    return dict(row) if row else None


def create_outreach(d: dict) -> int:
    cols = [k for k in OUTREACH_FIELDS if k in d]
    sql = f"INSERT INTO email_outreach ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    with db() as conn:
        return conn.execute(sql, [d[c] for c in cols]).lastrowid


def update_outreach(outreach_id: int, d: dict) -> None:
    cols = [k for k in OUTREACH_FIELDS if k in d]
    sets = ", ".join(f"{c}=?" for c in cols) + ", updated_at=CURRENT_TIMESTAMP"
    with db() as conn:
        conn.execute(f"UPDATE email_outreach SET {sets} WHERE id=?", [d[c] for c in cols] + [outreach_id])


def get_sender_by_email(email: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM sender_accounts WHERE lower(email_address)=?",
                           (email.lower(),)).fetchone()
    return dict(row) if row else None


def _latest(where: str, params: list, exclude_id: int | None) -> dict | None:
    sql = ("SELECT id, company_name, recipient_email, date_sent FROM email_outreach "
           f"WHERE deleted_at IS NULL AND {where}")
    if exclude_id:
        sql += " AND id != ?"
        params = params + [exclude_id]
    sql += " ORDER BY date_sent DESC LIMIT 1"
    with db() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def find_outreach_by_email(email: str, exclude_id: int | None = None) -> dict | None:
    return _latest("lower(recipient_email)=?", [email.lower()], exclude_id)


def find_outreach_by_domain(domain: str, days: int, exclude_id: int | None = None) -> dict | None:
    since = (date.today() - timedelta(days=days)).isoformat()
    return _latest("recipient_domain=? AND date(date_sent)>=?", [domain.lower(), since], exclude_id)


def find_outreach_by_company(name: str, exclude_id: int | None = None) -> dict | None:
    return _latest("lower(company_name)=lower(?)", [name], exclude_id)


# ---------- Phase 4A Outreach Listing & Operations ----------
import json

FOLLOWUP_EXCLUDED_STATUSES = ('Replied', 'Interested', 'Meeting Scheduled', 'Won', 'Lost', 'Not Interested')

ALLOWED_SORT_COLUMNS = {
    "date_sent": "o.date_sent",
    "company_name": "o.company_name",
    "recipient_email": "o.recipient_email",
    "sender_email": "s.email_address",
    "subject": "o.subject",
    "quoted_amount": "o.quoted_amount",
    "status": "o.status",
    "follow_up_date": "o.follow_up_date",
    "priority": "o.priority",
    "created_at": "o.created_at",
    "id": "o.id",
}


def list_outreach(
    filters: dict | None = None,
    sort_by: str = "date_sent",
    sort_dir: str = "desc",
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[dict], int]:
    filters = filters or {}
    where_clauses: list[str] = []
    params: list = []

    include_deleted = filters.get("include_deleted", False)
    if include_deleted:
        where_clauses.append("o.deleted_at IS NOT NULL")
    else:
        where_clauses.append("o.deleted_at IS NULL")

    search = (filters.get("search") or "").strip()
    if search:
        pattern = f"%{search}%"
        where_clauses.append(
            "(o.company_name LIKE ? OR o.recipient_email LIKE ? OR o.subject LIKE ? "
            "OR o.city LIKE ? OR o.contact_name LIKE ?)"
        )
        params.extend([pattern, pattern, pattern, pattern, pattern])

    status = filters.get("status")
    if status and status != "All":
        if isinstance(status, (list, tuple, set)):
            placeholders = ", ".join("?" for _ in status)
            where_clauses.append(f"o.status IN ({placeholders})")
            params.extend(status)
        else:
            where_clauses.append("o.status = ?")
            params.append(status)

    sender_id = filters.get("sender_id")
    if sender_id and sender_id != "All":
        try:
            where_clauses.append("o.sender_account_id = ?")
            params.append(int(sender_id))
        except (ValueError, TypeError):
            pass

    campaign = filters.get("campaign")
    if campaign and campaign != "All":
        where_clauses.append("o.campaign = ?")
        params.append(campaign)

    priority = filters.get("priority")
    if priority and priority != "All":
        where_clauses.append("o.priority = ?")
        params.append(priority)

    date_from = filters.get("date_from")
    if date_from:
        where_clauses.append("date(o.date_sent) >= ?")
        params.append(str(date_from)[:10])

    date_to = filters.get("date_to")
    if date_to:
        where_clauses.append("date(o.date_sent) <= ?")
        params.append(str(date_to)[:10])

    if filters.get("followup_due_only"):
        today_iso = date.today().isoformat()
        placeholders = ", ".join("?" for _ in FOLLOWUP_EXCLUDED_STATUSES)
        where_clauses.append(
            f"(o.follow_up_date IS NOT NULL AND date(o.follow_up_date) <= ? AND "
            f"o.follow_up_done = 0 AND o.status NOT IN ({placeholders}))"
        )
        params.append(today_iso)
        params.extend(FOLLOWUP_EXCLUDED_STATUSES)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    col = ALLOWED_SORT_COLUMNS.get(sort_by, "o.date_sent")
    direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"

    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM email_outreach o
        LEFT JOIN sender_accounts s ON o.sender_account_id = s.id
        WHERE {where_sql}
    """

    data_sql = f"""
        SELECT o.*, s.email_address AS sender_email, s.display_name AS sender_name
        FROM email_outreach o
        LEFT JOIN sender_accounts s ON o.sender_account_id = s.id
        WHERE {where_sql}
        ORDER BY {col} {direction}
        LIMIT ? OFFSET ?
    """

    with db() as conn:
        total = conn.execute(count_sql, params).fetchone()["total"]
        rows = [dict(r) for r in conn.execute(data_sql, params + [max(1, limit), max(0, offset)]).fetchall()]

    return rows, total


def outreach_metrics() -> dict:
    today_iso = date.today().isoformat()
    today_obj = date.today()
    week_start_iso = (today_obj - timedelta(days=today_obj.weekday())).isoformat()
    placeholders = ", ".join("?" for _ in FOLLOWUP_EXCLUDED_STATUSES)

    with db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM email_outreach WHERE deleted_at IS NULL"
        ).fetchone()["c"]

        sent_week = conn.execute(
            "SELECT COUNT(*) AS c FROM email_outreach WHERE deleted_at IS NULL AND date(date_sent) >= ?",
            (week_start_iso,),
        ).fetchone()["c"]

        replies = conn.execute(
            "SELECT COUNT(*) AS c FROM email_outreach WHERE deleted_at IS NULL AND "
            "(status IN ('Replied', 'Interested', 'Meeting Scheduled', 'Won') OR reply_date IS NOT NULL)"
        ).fetchone()["c"]

        fu_due = conn.execute(
            f"SELECT COUNT(*) AS c FROM email_outreach WHERE deleted_at IS NULL AND follow_up_date IS NOT NULL "
            f"AND date(follow_up_date) <= ? AND follow_up_done = 0 AND status NOT IN ({placeholders})",
            (today_iso, *FOLLOWUP_EXCLUDED_STATUSES),
        ).fetchone()["c"]

    return {
        "total": total,
        "sent_this_week": sent_week,
        "replies": replies,
        "followups_due": fu_due,
    }


def soft_delete_outreach(ids: list[int] | int) -> None:
    id_list = [ids] if isinstance(ids, int) else list(ids)
    if not id_list:
        return
    placeholders = ", ".join("?" for _ in id_list)
    with db() as conn:
        conn.execute(
            f"UPDATE email_outreach SET deleted_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
            id_list,
        )


def restore_outreach(ids: list[int] | int) -> None:
    id_list = [ids] if isinstance(ids, int) else list(ids)
    if not id_list:
        return
    placeholders = ", ".join("?" for _ in id_list)
    with db() as conn:
        conn.execute(
            f"UPDATE email_outreach SET deleted_at=NULL WHERE id IN ({placeholders})",
            id_list,
        )


def permanent_delete_outreach(ids: list[int] | int) -> None:
    id_list = [ids] if isinstance(ids, int) else list(ids)
    if not id_list:
        return
    placeholders = ", ".join("?" for _ in id_list)
    with db() as conn:
        conn.execute(
            f"DELETE FROM email_outreach WHERE id IN ({placeholders})",
            id_list,
        )


def list_trash() -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT o.*, s.email_address AS sender_email FROM email_outreach o "
            "LEFT JOIN sender_accounts s ON o.sender_account_id = s.id "
            "WHERE o.deleted_at IS NOT NULL ORDER BY o.deleted_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def empty_trash() -> int:
    with db() as conn:
        cur = conn.execute("DELETE FROM email_outreach WHERE deleted_at IS NOT NULL")
        return cur.rowcount


def update_outreach_status(ids: list[int] | int, status: str) -> None:
    id_list = [ids] if isinstance(ids, int) else list(ids)
    if not id_list:
        return
    placeholders = ", ".join("?" for _ in id_list)
    with db() as conn:
        conn.execute(
            f"UPDATE email_outreach SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
            [status] + id_list,
        )


def list_dnc() -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM do_not_contact ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def add_dnc(value: str, reason: str = "") -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO do_not_contact (value, reason) VALUES (?, ?)",
            ((value or "").strip().lower(), (reason or "").strip() or None),
        )
        return cur.lastrowid


def remove_dnc(dnc_id: int) -> None:
    with db() as conn:
        conn.execute("DELETE FROM do_not_contact WHERE id=?", (dnc_id,))


def get_saved_filters() -> dict:
    val = get_setting("saved_filters", "{}")
    try:
        data = json.loads(val)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def save_saved_filter(name: str, filters: dict) -> None:
    current = get_saved_filters()
    current[name] = filters
    set_setting("saved_filters", json.dumps(current))


def delete_saved_filter(name: str) -> None:
    current = get_saved_filters()
    if name in current:
        del current[name]
        set_setting("saved_filters", json.dumps(current))


# ---------- Desktop Widget / Time & Counters ----------
TIME_CATEGORIES = ["Working", "Gaming", "Rest", "Other"]
WORK_CATEGORIES = ["Working"]


def get_active_session() -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM time_sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def start_session(category: str, note: str = "") -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO time_sessions (category, started_at, note) VALUES (?, CURRENT_TIMESTAMP, ?)",
            (category, note or None),
        )
        return cur.lastrowid


def stop_session(session_id: int) -> None:
    with db() as conn:
        conn.execute(
            """UPDATE time_sessions
               SET ended_at = CURRENT_TIMESTAMP,
                   duration_seconds = max(0, round((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400))
               WHERE id = ?""",
            (session_id,),
        )


def time_totals_today() -> list[tuple[str, int]]:
    today_iso = date.today().isoformat()
    with db() as conn:
        rows = conn.execute(
            """SELECT category, COALESCE(SUM(
                CASE WHEN ended_at IS NOT NULL THEN duration_seconds
                     ELSE max(0, round((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400))
                END), 0) AS total_sec
               FROM time_sessions
               WHERE date(started_at) = ?
               GROUP BY category""",
            (today_iso,),
        ).fetchall()
    return [(r["category"], int(r["total_sec"])) for r in rows]


def time_by_day(days: int = 7) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with db() as conn:
        rows = conn.execute(
            """SELECT date(started_at) as log_date, category, SUM(duration_seconds) as total_sec
               FROM time_sessions
               WHERE date(started_at) >= ?
               GROUP BY date(started_at), category
               ORDER BY log_date""",
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def counter_get(name: str, log_date: str | None = None) -> int:
    d = log_date or date.today().isoformat()
    with db() as conn:
        row = conn.execute(
            "SELECT count FROM counter_log WHERE counter_name=? AND log_date=?",
            (name, d),
        ).fetchone()
    return row["count"] if row else 0


def counter_add(name: str, delta: int = 1, log_date: str | None = None) -> int:
    d = log_date or date.today().isoformat()
    with db() as conn:
        conn.execute(
            """INSERT INTO counter_log (log_date, counter_name, count)
               VALUES (?, ?, ?)
               ON CONFLICT(log_date, counter_name) DO UPDATE SET count = max(0, count + excluded.count)""",
            (d, name, delta),
        )
    return counter_get(name, d)


def counter_total(name: str) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS total FROM counter_log WHERE counter_name=?",
            (name,),
        ).fetchone()
    return int(row["total"]) if row else 0


def counter_by_day(name: str, days: int = 7) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with db() as conn:
        rows = conn.execute(
            """SELECT log_date, count FROM counter_log
               WHERE counter_name=? AND log_date >= ?
               ORDER BY log_date""",
            (name, since),
        ).fetchall()
    return [dict(r) for r in rows]