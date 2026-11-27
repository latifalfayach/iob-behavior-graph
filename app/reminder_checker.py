"""Deadline-driven reminder checker.

Instead of polling blindly on a fixed cron, we compute the NEXT time anything
could need attention (a reminder deadline or an auto-close deadline) and sleep
until exactly then. Run it as a loop:

    python reminder_checker.py --loop

Or run a single check (e.g. from GitHub Actions cron):

    python reminder_checker.py

Rules
-----
- After SILENCE_MIN minutes without a new event and without a closed session,
  send a gentle push. Repeat every REMIND_EVERY_MIN, give up after GIVE_UP_AFTER_H.
- At AUTO_CLOSE_HOUR (local server time), close orphan sessions automatically.
- The push payload carries the participant's personal token URL so the
  notification opens the app already logged in.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta

from pywebpush import webpush, WebPushException

import sheets_client

SILENCE_MIN = 15        # quiet this long -> send a check-in
REMIND_EVERY_MIN = 30   # never check in more often than this
GIVE_UP_AFTER_H = 4     # stop after this many hours of silence
APP_URL = "https://iob-behavior-graph-ehfisophxqtinrgvxsxryr.streamlit.app"   
VAPID_PRIVATE_KEY_PATH = "../secrets/private_key.pem"
VAPID_PUBLIC_KEY_PATH ="../app/public_key.pem"
VAPID_CLAIMS = {"sub": "mailto:lfayach@gmail.com"}   
AUTO_CLOSE_HOUR = 23   # local time; mornings still open after this get auto-closed


def _now():
    return datetime.now(timezone.utc)


def _parse(value):
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def send_push(subscription_json, user_id, token):
    try:
        with open(VAPID_PRIVATE_KEY_PATH) as f:
            private_key = f.read().strip()
    except Exception as e:
        print(f"  [push] cannot read VAPID key: {e}")
        return False

    url = f"{APP_URL}?token={token}" if token else APP_URL
    try:
        webpush(
            subscription_info=json.loads(subscription_json),
            data=json.dumps({
                "title": "☀️ Morning Companion",
                "body": "Quick check-in — what are you up to?",
                "url": url,
            }),
            vapid_private_key=private_key,
            vapid_claims=VAPID_CLAIMS,
        )
        return True
    except WebPushException as e:
        print(f"  [push] failed for {user_id}: {e}")
        return False


def check():
    """One pass: send due reminders, return the next deadline (datetime, UTC)."""
    now = _now()
    next_deadline = now + timedelta(minutes=10)   # fallback

    try:
        subs = sheets_client.get_push_subscriptions()
    except Exception as e:
        print(f"[check] cannot read push tab: {e}")
        return next_deadline

    for row in subs:
        uid = row.get("user_id", "")
        sub_json = row.get("subscription_json", "")
        tok = (row.get("token") or "").strip()
        if not uid or not sub_json:
            continue

        # already finished today? nothing to do
        if sheets_client.load_today_session(uid):
            continue

        events = sheets_client.load_today_events(uid)
        now_local = datetime.now().astimezone()

        if not events:
            # no events yet today: remind only during morning hours
            if now_local.hour < AUTO_CLOSE_HOUR:
                last = _parse(row.get("last_reminder_utc", ""))
                if not last or (now - last) > timedelta(minutes=REMIND_EVERY_MIN):
                    if send_push(sub_json, uid, tok):
                        sheets_client.update_push_reminder(uid, now.isoformat(timespec="seconds"))
                        print(f"[check] reminded {uid} (no events yet)")
                    next_deadline = min(next_deadline, now + timedelta(minutes=REMIND_EVERY_MIN))
                else:
                    next_deadline = min(next_deadline,
                                        last + timedelta(minutes=REMIND_EVERY_MIN))
            continue

        last_ts = _parse(events[-1].get("ts_utc"))
        if not last_ts:
            continue
        silence = now - last_ts

        if silence > timedelta(hours=GIVE_UP_AFTER_H):
            continue  # gave up — auto-close will handle it at midday

        last_reminder = _parse(row.get("last_reminder_utc", ""))
        due_at = last_ts + timedelta(minutes=SILENCE_MIN)
        if last_reminder:
            due_at = max(due_at, last_reminder + timedelta(minutes=REMIND_EVERY_MIN))

        if now >= due_at:
            if send_push(sub_json, uid, tok):
                sheets_client.update_push_reminder(uid, now.isoformat(timespec="seconds"))
                print(f"[check] reminded {uid} after {int(silence.total_seconds()//60)} min silence")
            next_deadline = min(next_deadline, now + timedelta(minutes=REMIND_EVERY_MIN))
        else:
            next_deadline = min(next_deadline, due_at)

    close_orphan_sessions()
    return next_deadline


def close_orphan_sessions():
    """Auto-close sessions that were started but never finished, at midday."""
    now_local = datetime.now().astimezone()
    if now_local.hour != AUTO_CLOSE_HOUR:
        return
    today = now_local.date().isoformat()

    try:
        users = sheets_client.load_users()
    except Exception:
        return

    for uid in users:
        if sheets_client.load_today_session(uid):
            continue
        events = sheets_client.load_today_events(uid)
        if len(events) < 3:
            continue
        t0, t1 = _parse(events[0].get("ts_utc")), _parse(events[-1].get("ts_utc"))
        row = {
            "session_id": f"{uid}_{today}",
            "user_id": uid,
            "session_date": today,
            "n_events": len(events),
            "chain": ">".join(e["activity_id"] for e in events),
            "duration_min": round((t1 - t0).total_seconds() / 60, 1) if t0 and t1 else "",
            "complete": True,
            "closed_by": "auto",
        }
        try:
            sheets_client.append_session(row)
            print(f"[auto-close] closed orphan session for {uid}")
        except Exception as e:
            print(f"[auto-close] failed for {uid}: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true",
                        help="keep running, sleeping until each next deadline")
    args = parser.parse_args()

    if not args.loop:
        check()
        return

    print("[loop] deadline-driven reminder checker started")
    while True:
        try:
            deadline = check()
        except Exception as e:
            print(f"[loop] check failed: {e}")
            deadline = _now() + timedelta(minutes=10)
        sleep_s = max(30, (deadline - _now()).total_seconds())
        print(f"[loop] sleeping {int(sleep_s)}s until {deadline.isoformat(timespec='seconds')}")
        time.sleep(sleep_s)


if __name__ == "__main__":
    sys.exit(main())
