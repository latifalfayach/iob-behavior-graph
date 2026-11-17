"""Gentle inactivity check-ins via Web Push. Run: python reminder_checker.py [--loop]"""
import argparse
import json
import time
from datetime import datetime, timezone, timedelta

from pywebpush import webpush, WebPushException
import sheets_client

SILENCE_MIN = 15        # quiet this long -> send a check-in
REMIND_EVERY_MIN = 30   # never check in more often than this
GIVE_UP_AFTER_H = 4     # stop after this many hours of silence
APP_URL = "https://latifalfayach.github.io/morning-companion/"   # <-- set after deployment
VAPID_PRIVATE = "../secrets/private_key.pem"
VAPID_CLAIMS = {"sub": "mailto:lfayach@gmail.com"}   # <-- your email


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
        except Exception:
            continue
        silent = now - last_ts
        if silent < timedelta(minutes=SILENCE_MIN) or silent > timedelta(hours=GIVE_UP_AFTER_H):
            continue
        prev = str(row.get("last_reminder_utc", "") or "")
        if prev:
            try:
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
                    "url": APP_URL,
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
    parser.add_argument("--loop", action="store_true", help="repeat every 10 minutes")
    args = parser.parse_args()
    if args.loop:
        print("Reminder service running (checks every 10 min). Ctrl+C to stop.")
        while True:
            check()
            time.sleep(600)
    else:
        check()