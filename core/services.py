"""Business logic on top of the repository."""
import re
import sqlite3
from datetime import date, datetime, timedelta

from core import repository as repo

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GENERIC_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "live.com"}
_EMAIL_FIND = re.compile(r"[^@\s,<>;()]+@[^@\s,<>;()]+\.[^@\s,<>;()]+")


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match((value or "").strip()))


def domain_of(email: str) -> str:
    return email.split("@")[-1].strip().lower() if "@" in (email or "") else ""


def _s(v):
    if v is None:
        return None
    v = str(v).strip()
    return v or None


# ---------------------------------------------------------------- sender limits
def effective_daily_limit(sender: dict) -> int:
    """Warm-up: days 1-7 = 5/day, days 8-14 = 10/day, then the normal limit."""
    limit = int(sender.get("daily_limit") or 0)
    if sender.get("warmup_enabled") and sender.get("warmup_start_date"):
        try:
            start = date.fromisoformat(str(sender["warmup_start_date"]))
            day = max(1, (date.today() - start).days + 1)
            if day <= 7:
                return min(5, limit)
            if day <= 14:
                return min(10, limit)
        except ValueError:
            pass
    return limit


def sent_today(sender_id: int) -> int:
    return repo.count_sent_today(sender_id)


def usage_summary() -> list[dict]:
    """Every usable account with today's count, limit, remaining and state."""
    out = []
    for s in repo.list_senders():
        if not s["is_active"] or s["status"] != "active":
            continue
        limit = effective_daily_limit(s)
        used = s["sent_today"]
        pct = (used / limit) if limit else 0
        state = "red" if pct >= 1 else "amber" if pct >= 0.7 else "green"
        out.append({
            "id": s["id"], "email": s["email_address"], "display_name": s["display_name"],
            "sent_today": used, "limit": limit, "remaining": max(0, limit - used), "state": state,
        })
    return out


def sender_usage(sender_id: int) -> dict | None:
    """Usage for one account (works even for resting/inactive ones)."""
    s = repo.get_sender(sender_id)
    if not s:
        return None
    limit = effective_daily_limit(s)
    used = repo.count_sent_today(sender_id)
    pct = (used / limit) if limit else 0
    return {
        "id": s["id"], "email": s["email_address"], "sent_today": used, "limit": limit,
        "remaining": max(0, limit - used),
        "state": "red" if pct >= 1 else "amber" if pct >= 0.7 else "green",
    }


def next_available_sender() -> dict | None:
    """The usable account with the most remaining capacity today."""
    candidates = [u for u in usage_summary() if u["remaining"] > 0]
    return max(candidates, key=lambda u: u["remaining"]) if candidates else None


def limit_alerts() -> list[str]:
    return [
        f"{u['email']} reached today's limit ({u['sent_today']}/{u['limit']})"
        for u in usage_summary() if u["limit"] > 0 and u["sent_today"] >= u["limit"]
    ]


def save_sender(data: dict, sender_id: int | None = None) -> tuple[bool, str]:
    email = (data.get("email_address") or "").strip().lower()
    if not is_valid_email(email):
        return False, "Enter a valid email address."
    try:
        limit = int(data.get("daily_limit") or 0)
    except (TypeError, ValueError):
        limit = 0
    if limit < 1:
        return False, "Daily limit must be at least 1."

    status = data.get("status") or "active"
    warm = bool(data.get("warmup_enabled"))
    reason = (data.get("status_reason") or "").strip() or None
    clean = {
        "email_address": email,
        "display_name": (data.get("display_name") or "").strip() or None,
        "daily_limit": limit,
        "status": status,
        "status_reason": reason if status != "active" else None,
        "warmup_enabled": 1 if warm else 0,
        "warmup_start_date": (data.get("warmup_start_date") or date.today().isoformat()) if warm else None,
        "notes": (data.get("notes") or "").strip() or None,
    }
    try:
        if sender_id:
            repo.update_sender(sender_id, clean)
            repo.log_activity("update", "sender", sender_id, f"Updated sender {email}")
            return True, "Sender updated."
        new_id = repo.create_sender(clean)
        repo.log_activity("create", "sender", new_id, f"Added sender {email}")
        return True, "Sender added."
    except sqlite3.IntegrityError:
        return False, "That email address already exists."


# ---------------------------------------------------------------- add-outreach helpers
def parse_paste(text: str) -> tuple[str, str]:
    """'Acme Corp, john@acme.com' or 'Acme <john@acme.com>' -> (company, email)."""
    text = text or ""
    m = _EMAIL_FIND.search(text)
    email = m.group(0).lower() if m else ""
    rest = text.replace(m.group(0), " ") if m else text
    company = re.sub(r"[,;<>()|]+", " ", rest)
    company = re.sub(r"\s+", " ", company).strip(" -:")
    return company, email


def fill_template(text: str, company: str, contact: str, final: bool = False) -> str:
    """Replace {company}/{contact}. With final=True, leftovers get safe fallbacks."""
    text = text or ""
    c, k = (company or "").strip(), (contact or "").strip()
    if c or final:
        text = text.replace("{company}", c or "your company")
    if k or final:
        text = text.replace("{contact}", k or "there")
    return text


def check_warnings(email: str, company: str, exclude_id: int | None = None) -> list[dict]:
    """Non-blocking warnings shown under the Company/Email fields."""
    out: list[dict] = []
    email = (email or "").strip().lower()
    company = (company or "").strip()
    seen: set[int] = set()
    domain = domain_of(email) if is_valid_email(email) else ""

    if domain:
        dnc = repo.find_dnc(email, domain)
        if dnc:
            reason = f" ({dnc['reason']})" if dnc.get("reason") else ""
            out.append({"level": "danger", "id": None,
                        "text": f"Do Not Contact list: {dnc['value']}{reason}"})
        prev = repo.find_outreach_by_email(email, exclude_id)
        if prev:
            seen.add(prev["id"])
            out.append({"level": "warn", "id": prev["id"],
                        "text": f"You already emailed this address on {str(prev['date_sent'])[:10]} "
                                f"({prev['company_name']})."})
        if domain not in GENERIC_DOMAINS:
            days = int(repo.get_setting("domain_cooldown_days", "14") or 14)
            rec = repo.find_outreach_by_domain(domain, days, exclude_id)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                out.append({"level": "warn", "id": rec["id"],
                            "text": f"Same domain ({domain}) emailed on {str(rec['date_sent'])[:10]}, "
                                    f"inside your {days}-day cooldown."})
    if company:
        c = repo.find_outreach_by_company(company, exclude_id)
        if c and c["id"] not in seen:
            out.append({"level": "warn", "id": c["id"],
                        "text": f"'{company}' already exists (emailed {str(c['date_sent'])[:10]})."})
    return out


def save_outreach(data: dict, outreach_id: int | None = None) -> tuple[bool, str, int | None]:
    company = _s(data.get("company_name"))
    email = (_s(data.get("recipient_email")) or "").lower()
    if not company:
        return False, "Company name is required.", None
    if not is_valid_email(email):
        return False, "Enter a valid recipient email.", None
    sid = data.get("sender_account_id")
    if not sid or not repo.get_sender(sid):
        return False, "Select a sender account.", None

    raw = _s(data.get("date_sent"))
    try:
        dt = datetime.fromisoformat(raw) if raw else datetime.now()
    except ValueError:
        return False, "Invalid date/time sent.", None

    follow = _s(data.get("follow_up_date"))
    if follow:
        try:
            date.fromisoformat(follow)
        except ValueError:
            return False, "Invalid follow-up date.", None
    elif not outreach_id:
        days = int(repo.get_setting("default_followup_days", "7") or 7)
        follow = (dt.date() + timedelta(days=days)).isoformat()

    amount = data.get("quoted_amount")
    try:
        amount = float(amount) if amount not in (None, "") else None
    except (TypeError, ValueError):
        return False, "Quoted amount must be a number.", None

    contact = _s(data.get("contact_name"))
    row = {
        "date_sent": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "company_name": company, "recipient_email": email, "recipient_domain": domain_of(email),
        "sender_account_id": sid,
        "city": _s(data.get("city")), "website": _s(data.get("website")),
        "contact_name": contact, "job_title": _s(data.get("job_title")),
        "linkedin_url": _s(data.get("linkedin_url")),
        "subject": fill_template(_s(data.get("subject")) or "", company, contact or "", final=True) or None,
        "email_body": fill_template(_s(data.get("email_body")) or "", company, contact or "", final=True) or None,
        "campaign": _s(data.get("campaign")), "template_id": data.get("template_id") or None,
        "lead_source": _s(data.get("lead_source")), "priority": _s(data.get("priority")) or "Medium",
        "tags": _s(data.get("tags")), "status": _s(data.get("status")) or "Sent",
        "next_action": _s(data.get("next_action")), "quoted_amount": amount,
        "currency": _s(data.get("currency")) or "USD", "follow_up_date": follow,
        "notes": _s(data.get("notes")),
    }
    if outreach_id:
        repo.update_outreach(outreach_id, row)
        repo.log_activity("update", "outreach", outreach_id, f"Updated outreach to {company}")
        return True, "Entry updated.", outreach_id
    new_id = repo.create_outreach(row)
    repo.log_activity("create", "outreach", new_id, f"Logged outreach to {company}")
    return True, "Outreach added.", new_id


# ---------------------------------------------------------------- Phase 4A Outreach Actions
def soft_delete_outreach(ids: list[int] | int) -> None:
    id_list = [ids] if isinstance(ids, int) else list(ids)
    if not id_list:
        return
    repo.soft_delete_outreach(id_list)
    repo.log_activity("soft_delete", "outreach", id_list[0] if len(id_list) == 1 else None,
                      f"Moved {len(id_list)} outreach entry(ies) to trash")


def restore_outreach(ids: list[int] | int) -> None:
    id_list = [ids] if isinstance(ids, int) else list(ids)
    if not id_list:
        return
    repo.restore_outreach(id_list)
    repo.log_activity("restore", "outreach", id_list[0] if len(id_list) == 1 else None,
                      f"Restored {len(id_list)} outreach entry(ies) from trash")


def permanent_delete_outreach(ids: list[int] | int) -> None:
    id_list = [ids] if isinstance(ids, int) else list(ids)
    if not id_list:
        return
    repo.permanent_delete_outreach(id_list)
    repo.log_activity("permanent_delete", "outreach", id_list[0] if len(id_list) == 1 else None,
                      f"Permanently deleted {len(id_list)} outreach entry(ies)")


def empty_trash() -> int:
    count = repo.empty_trash()
    repo.log_activity("empty_trash", "outreach", None, f"Emptied trash ({count} items)")
    return count


def update_status(ids: list[int] | int, status: str) -> None:
    id_list = [ids] if isinstance(ids, int) else list(ids)
    if not id_list:
        return
    repo.update_outreach_status(id_list, status)
    repo.log_activity("update_status", "outreach", id_list[0] if len(id_list) == 1 else None,
                      f"Updated status to {status} for {len(id_list)} entry(ies)")


def mark_followup_done(outreach_id: int) -> None:
    repo.update_outreach(outreach_id, {"follow_up_done": 1})
    repo.log_activity("followup_done", "outreach", outreach_id,
                      f"Marked follow-up done for outreach #{outreach_id}")


def export_outreach(filters: dict, sort_by: str = "date_sent", sort_dir: str = "desc", fmt: str = "csv"):
    from pathlib import Path
    from core.exports import export_outreach_to_file
    rows, _ = repo.list_outreach(filters, sort_by=sort_by, sort_dir=sort_dir, limit=100000, offset=0)
    filepath = export_outreach_to_file(rows, fmt=fmt)
    repo.log_activity("export", "outreach", None, f"Exported {len(rows)} outreach rows to {filepath.name}")
    return filepath


# ---------------------------------------------------------------- Do Not Contact Helpers
def clean_dnc_value(raw: str) -> str:
    val = (raw or "").strip().lower()
    if val.startswith("@"):
        val = val[1:].strip()
    if val.startswith("www."):
        val = val[4:].strip()
    return val


def add_dnc_entry(raw_value: str, reason: str = "") -> tuple[bool, str]:
    val = clean_dnc_value(raw_value)
    if not val or " " in val or "." not in val:
        return False, "Enter a valid email address or domain (e.g. example.com or user@example.com)."
    existing = repo.list_dnc()
    if any(d["value"].lower() == val for d in existing):
        return False, f"'{val}' is already on the Do Not Contact list."
    dnc_id = repo.add_dnc(val, reason)
    repo.log_activity("add_dnc", "do_not_contact", dnc_id, f"Added {val} to Do Not Contact list")
    return True, f"Added {val} to Do Not Contact list."


def remove_dnc_entry(dnc_id: int) -> None:
    repo.remove_dnc(dnc_id)
    repo.log_activity("remove_dnc", "do_not_contact", dnc_id, f"Removed entry #{dnc_id} from Do Not Contact list")