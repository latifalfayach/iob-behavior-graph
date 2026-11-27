"""Gentle inactivity check-ins via Web Push. Run: python reminder_checker.py [--loop]"""
import argparse
import json
import time
from datetime import datetime, timezone, timedelta, date

from pywebpush import webpush, WebPushException
import sheets_client

SILENCE_MIN = 15        # quiet this long -> send a check-in
REMIND_EVERY_MIN = 15   # never check in more often than this
GIVE_UP_AFTER_H = 4     # stop after this many hours of silence
APP_URL = "https://iob-behavior-graph-ehfisophxqtinrgvxsxryr.streamlit.app/"   # <-- set after deployment
VAPID_PRIVATE = "../secrets/private_key.pem"
VAPID_CLAIMS = {"sub": "mailto:lfayach@gmail.com"}   # <-- your email
AUTO_CLOSE_HOUR = 23   # local time; mornings still open after this get auto-closed

def next_deadline():
    """Earliest moment at which someone will become eligible for a check-in."""
    now = datetime.now(timezone.utc)
    deadlines = []
    for row in sheets_client.get_push_subscriptions():
        uid = str(row.get("user_id", "")).strip()
        if not uid or sheets_client.load_today_session(uid):
            continue
        events = sheets_client.load_today_events(uid)
        if not events:
            continue
        try:
            last_ts = datetime.fromisoformat(str(events[-1]["ts_utc"]))
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if now - last_ts > timedelta(hours=GIVE_UP_AFTER_H):
            continue
        deadline = last_ts + timedelta(minutes=SILENCE_MIN)
        prev = str(row.get("last_reminder_utc", "") or "")
        if prev:
            try:  # respect the anti-spam interval
                prev_dt = datetime.fromisoformat(prev)
                if prev_dt.tzinfo is None:
                    prev_dt = prev_dt.replace(tzinfo=timezone.utc)
                deadline = max(deadline,
                               datetime.fromisoformat(prev) + timedelta(minutes=REMIND_EVERY_MIN))
            except Exception:
                pass
        deadlines.append(deadline)
    return min(deadlines) if deadlines else None

def close_orphan_sessions():
    """Auto-close today's unfinished mornings (participant never tapped an end button)."""
    now_local = datetime.now().astimezone()
    if now_local.hour < AUTO_CLOSE_HOUR:
        return                                    # morning window still open
    for uid in sheets_client.load_users():
        if sheets_client.load_today_session(uid):
            continue                              # already closed (by user or earlier run)
        events = sheets_client.load_today_events(uid)
        if len(events) < 3:
            continue                              # raw-only tier: keep events, no session row
        try:
            t0 = datetime.fromisoformat(str(events[0]["ts_utc"]))
            t1 = datetime.fromisoformat(str(events[-1]["ts_utc"]))
            duration = round((t1 - t0).total_seconds() / 60, 1)
        except Exception:
            duration = ""
        sheets_client.append_session({
            "session_id": f"{uid}_{date.today().isoformat()}",
            "user_id": uid,
            "session_date": date.today().isoformat(),
            "n_events": len(events),
            "chain": ">".join(str(e["activity_id"]) for e in events),
            "duration_min": duration,
            "complete": False,
            "closed_by": "auto",
        })
        print(f"Auto-closed orphan session for {uid} ({len(events)} events)")


def check():
    now = datetime.now(timezone.utc)
    for row in sheets_client.get_push_subscriptions():
        uid = str(row.get("user_id", "")).strip()
        sub_raw = str(row.get("subscription_json", "")).strip()
        if not uid or not sub_raw:
            continue
        if sheets_client.load_today_session(uid):
            continue                                   # morning finished
        events = sheets_client.load_today_events(uid)
        if not events:
            continue                                   # morning not started
        try:
            last_ts = datetime.fromisoformat(str(events[-1]["ts_utc"]))
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        silent = now - last_ts
        if silent < timedelta(minutes=SILENCE_MIN) or silent > timedelta(hours=GIVE_UP_AFTER_H):
            continue
        prev = str(row.get("last_reminder_utc", "") or "")
        if prev:
            try:
                prev_dt = datetime.fromisoformat(prev)
                if prev_dt.tzinfo is None:
                    prev_dt = prev_dt.replace(tzinfo=timezone.utc)
                if now - datetime.fromisoformat(prev) < timedelta(minutes=REMIND_EVERY_MIN):
                    continue                           # don't nag
            except Exception:
                pass
        try:
            webpush(
                subscription_info=json.loads(sub_raw),
                data=json.dumps({
                    "title": "☀️ Quick check-in",
                    "body": "What are you up to? Tap to continue your morning 🌅",
                    "url": f"{APP_URL}?id={uid}",
                }),
                vapid_private_key=VAPID_PRIVATE,
                vapid_claims=VAPID_CLAIMS.copy(),
                ttl=3600,
            )
            sheets_client.update_push_reminder(uid, now.isoformat(timespec="seconds"))
            print(f"[{now:%H:%M}] Check-in sent to {uid}")
        except WebPushException as e:
            print(f"[{now:%H:%M}] Push failed for {uid}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="run continuously (deadline-driven)")
    args = parser.parse_args()
    if args.loop:
        print("Reminder service running (deadline-driven). Ctrl+C to stop.", flush=True)
        while True:
            check()
            close_orphan_sessions()
            wake = next_deadline()
            if wake is None:
                delay = 600                       # nobody mid-morning: rescan every 10 min
            else:
                delay = (wake - datetime.now(timezone.utc)).total_seconds()
                delay = max(30, min(600, delay))  # clamp: 30 s .. 10 min
            print(f"Next wake-up in {int(delay)} s", flush=True)
            time.sleep(delay)
    else:
        check()
        close_orphan_sessions()