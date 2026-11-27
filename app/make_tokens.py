"""One-off migration: generate a secret token + QR code for every EXISTING user.

Run this ONCE locally (from the app/ folder, with your service_account.json in
../secrets/ and qrcode installed) after adding the `tokens` tab to your Sheet:

    pip install qrcode[pil]
    python make_tokens.py

It creates one PNG per user in ./qr_codes/ — send each participant their own
QR privately. Raw tokens exist ONLY in these PNGs (and the link inside them);
the Sheet stores only the SHA-256 hash, so a Sheet leak cannot expose logins.

Users created after this migration get their token automatically from the app
(create_user already handles it), so you never need to run this script again.
"""
import io
import os
import secrets
import hashlib

import qrcode

import sheets_client

APP_URL = "https://iob-behavior-graph-ehfisophxqtinrgvxsxryr.streamlit.app"   
OUT_DIR = "qr_codes"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    users = sheets_client.load_users()
    if not users:
        print("No users found — nothing to do.")
        return

    for uid in users:
        if sheets_client.has_token(uid):
            print(f"  {uid}: already has a token, skipping")
            continue
        token = secrets.token_urlsafe(12)
        sheets_client.append_token(uid, token)

        link = f"{APP_URL}?token={token}"
        img = qrcode.make(link)
        path = os.path.join(OUT_DIR, f"qr_{uid}.png")
        img.save(path)
        print(f"  {uid}: token created -> {path}")
        print(f"        link: {link}")

    print("\nDone. Send each participant their own PNG privately.")
    print("Reminder: raw tokens exist only in these PNGs — keep the folder safe.")


if __name__ == "__main__":
    main()
