"""Google Sheets connection layer (Phase 4)."""
import hashlib
import secrets as _secrets
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

CREDENTIALS_FILE = "../secrets/service_account.json"

CREDENTIALS_FILE = "../secrets/service_account.json"
SHEET_ID = "17GfHPSW6CBb67IqSz7zxQ82dozlO5Xq2bGxaXMdKT2w"   
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_doc = None


def _get_doc():
    """Credentials priority (base64 first — it survives Streamlit secrets TOML
    with zero escaping issues, unlike raw JSON with \n in private_key):
      1. Streamlit secret GCP_SA_B64        (base64 of service_account.json)
      2. Streamlit secret GCP_SERVICE_ACCOUNT_JSON  (raw JSON, legacy)
      3. Environment variable GCP_SA_B64    (scripts / CI)
      4. Local file ../secrets/service_account.json (development)
    """
    global _doc
    if _doc is None:
        import base64
        import json
        import os
        creds = None

        def _from_b64(b64, where):
            try:
                info = json.loads(base64.b64decode(b64).decode("utf-8"))
                return Credentials.from_service_account_info(info, scopes=SCOPES)
            except Exception as e:
                raise RuntimeError(f"{where} exists but could not be decoded: {e}")

        try:
            import streamlit as st
            if "GCP_SA_B64" in st.secrets:
                creds = _from_b64(st.secrets["GCP_SA_B64"], "GCP_SA_B64 secret")
            elif "GCP_SERVICE_ACCOUNT_JSON" in st.secrets:
                try:
                    info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
                    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
                except Exception as e:
                    raise RuntimeError(
                        f"GCP_SERVICE_ACCOUNT_JSON exists but could not be parsed: {e}")
        except ModuleNotFoundError:
            pass  # not running inside Streamlit (local scripts)

        if creds is None and os.environ.get("GCP_SA_B64"):
            creds = _from_b64(os.environ["GCP_SA_B64"], "GCP_SA_B64 env var")

        if creds is None:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    "No credentials found. Cloud: set GCP_SA_B64 in Streamlit app "
                    "secrets (base64 of your service_account.json). Local: put "
                    "service_account.json in the secrets/ folder.")
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        _doc = client.open_by_key(SHEET_ID)
    return _doc


# ---------------- users ----------------
def load_users():
    """Return list of user_ids from the 'users' tab."""
    ws = _get_doc().worksheet("users")
    return [u for u in ws.col_values(1)[1:] if u.strip()]


def create_user():
    """Create the next participant ID + a secret token. Returns (user_id, token)."""
    ws = _get_doc().worksheet("users")
    existing = [u for u in ws.col_values(1)[1:] if u.strip()]
    nums = [int(u[1:]) for u in existing if u.startswith("U") and u[1:].isdigit()]
    new_id = f"U{max(nums, default=0) + 1:03d}"
    token = _secrets.token_urlsafe(12)          # e.g. '8fK2Lm91Xq7Pz4Ab'
    th = hashlib.sha256(token.encode()).hexdigest()
    ws.append_row([new_id, date.today().isoformat()], value_input_option="RAW")
    _get_doc().worksheet("tokens").append_row(
        [th, new_id, date.today().isoformat()], value_input_option="RAW")
    return new_id, token


# ---------------- tokens ----------------
def user_for_token(token: str):
    """Resolve a secret token to a user_id, or None if invalid."""
    th = hashlib.sha256(token.encode()).hexdigest()
    ws = _get_doc().worksheet("tokens")
    for r in ws.get_all_records():
        if str(r.get("token_hash")) == th:
            return str(r.get("user_id"))
    return None


def has_token(user_id: str) -> bool:
    ws = _get_doc().worksheet("tokens")
    return user_id in [str(u) for u in ws.col_values(2)[1:]]


def append_token(user_id: str, token: str):
    th = hashlib.sha256(token.encode()).hexdigest()
    _get_doc().worksheet("tokens").append_row(
        [th, user_id, date.today().isoformat()], value_input_option="RAW")


# ---------------- events ----------------
def append_event(row: dict):
    """Append one event row. RAW mode keeps our exact timestamp strings."""
    ws = _get_doc().worksheet("events")
    ws.append_row(
        [row["event_id"], row["user_id"], row["session_date"], row["seq_index"],
         row["activity_id"], row["ts_utc"], row["local_time"], row["day_type"],
         row["device"], row.get("source", "live")],
        value_input_option="RAW",
    )


def load_today_events(user_id: str):
    """Reload today's events so the UI survives page refreshes."""
    ws = _get_doc().worksheet("events")
    today = date.today().isoformat()
    rows = ws.get_all_records()
    events = [r for r in rows
              if str(r.get("user_id")) == user_id and str(r.get("session_date")) == today]
    events.sort(key=lambda r: int(float(r.get("seq_index") or 0)))
    return events


def delete_today_events(user_id: str):
    """Delete today's event rows for a user (used before a recap rewrite)."""
    ws = _get_doc().worksheet("events")
    today = date.today().isoformat()
    rows = ws.get_all_values()
    to_delete = [i for i, r in enumerate(rows[1:], start=2)
                 if len(r) > 2 and r[1] == user_id and r[2] == today]
    for i in reversed(to_delete):   # bottom-up so indices stay valid
        ws.delete_rows(i)


# ---------------- sessions ----------------
def append_session(row: dict):
    """Append one session row. closed_by: user / auto / recall."""
    ws = _get_doc().worksheet("sessions")
    ws.append_row(
        [row["session_id"], row["user_id"], row["session_date"], row["n_events"],
         row["chain"], row["duration_min"], row["complete"],
         row.get("closed_by", "user")],
        value_input_option="RAW",
    )


def load_today_session(user_id: str):
    """Return today's finished session row, or None if the morning is still open."""
    ws = _get_doc().worksheet("sessions")
    target = f"{user_id}_{date.today().isoformat()}"
    for r in ws.get_all_records():
        if str(r.get("session_id")) == target:
            return r
    return None


# ---------------- telegram (backup reminder channel) ----------------
def get_telegram_links():
    return _get_doc().worksheet("telegram").get_all_records()


def save_telegram_link(user_id: str, chat_id):
    ws = _get_doc().worksheet("telegram")
    try:
        cell = ws.find(user_id)
        ws.update_cell(cell.row, 2, str(chat_id))
    except gspread.CellNotFound:
        ws.append_row([user_id, str(chat_id), ""], value_input_option="RAW")


def update_last_reminder(user_id: str, iso_ts: str):
    ws = _get_doc().worksheet("telegram")
    cell = ws.find(user_id)
    ws.update_cell(cell.row, 3, iso_ts)


# ---------------- web push ----------------
def get_push_subscriptions():
    """All rows from the 'push' tab as dicts."""
    return _get_doc().worksheet("push").get_all_records()


def update_push_reminder(user_id: str, iso_ts: str):
    """Record when we last reminded this participant (anti-spam)."""
    ws = _get_doc().worksheet("push")
    cell = ws.find(user_id)
    ws.update_cell(cell.row, 4, iso_ts)
