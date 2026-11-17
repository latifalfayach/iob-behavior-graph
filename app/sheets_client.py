"""Google Sheets connection layer (Phase 4)."""
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

CREDENTIALS_FILE = "../secrets/service_account.json"
SHEET_ID = "17GfHPSW6CBb67IqSz7zxQ82dozlO5Xq2bGxaXMdKT2w"   
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_doc = None


def _get_doc():
    global _doc
    if _doc is None:
        import base64
        import json
        import os
        creds = None
        try:
            import streamlit as st
            if "GCP_SA_B64" in st.secrets:
                raw = base64.b64decode(st.secrets["GCP_SA_B64"]).decode("utf-8")
                info = json.loads(raw)
                creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        except ModuleNotFoundError:
            pass
        if creds is None:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError("No credentials found.")
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        _doc = client.open_by_key(SHEET_ID)
    return _doc

def load_users():
    """Return list of user_ids from the 'users' tab."""
    ws = _get_doc().worksheet("users")
    return [u for u in ws.col_values(1)[1:] if u.strip()]


def append_event(row: dict):
    """Append one event row. RAW mode keeps our exact timestamp strings."""
    ws = _get_doc().worksheet("events")
    ws.append_row(
        [row["event_id"], row["user_id"], row["session_date"], row["seq_index"],
         row["activity_id"], row["ts_utc"], row["local_time"], row["day_type"],
         row["device"]],
        value_input_option="RAW",
    )


def append_session(row: dict):
    ws = _get_doc().worksheet("sessions")
    ws.append_row(
        [row["session_id"], row["user_id"], row["session_date"], row["n_events"],
         row["chain"], row["duration_min"], row["complete"]],
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


def load_today_session(user_id: str):
    """Return today's finished session row, or None if the morning is still open."""
    ws = _get_doc().worksheet("sessions")
    target = f"{user_id}_{date.today().isoformat()}"
    for r in ws.get_all_records():
        if str(r.get("session_id")) == target:
            return r
    return None

def create_user():
    """Create the next sequential participant ID (U001, U002, ...) and register it."""
    ws = _get_doc().worksheet("users")
    existing = [u for u in ws.col_values(1)[1:] if u.strip()]
    nums = [int(u[1:]) for u in existing if u.startswith("U") and u[1:].isdigit()]
    new_id = f"U{max(nums, default=0) + 1:03d}"
    ws.append_row([new_id, date.today().isoformat()], value_input_option="RAW")
    return new_id

def get_push_subscriptions():
    """All rows from the 'push' tab as dicts."""
    return _get_doc().worksheet("push").get_all_records()


def update_push_reminder(user_id: str, iso_ts: str):
    """Record when we last reminded this participant (anti-spam)."""
    ws = _get_doc().worksheet("push")
    cell = ws.find(user_id)
    ws.update_cell(cell.row, 4, iso_ts)