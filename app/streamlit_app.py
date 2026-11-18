"""Morning Companion — calm, one-question-at-a-time UI (replaces the form-style v1)."""
import uuid
from datetime import datetime, timezone, date

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from activities import ACTIVITIES, ACTIVITY_BY_ID
import sheets_client

# ---------------- config ----------------
INACTIVITY_MIN = 12       # gentle check-in appears after this many quiet minutes
AUTOREFRESH_MS = 60_000   # page quietly refreshes once a minute (no push needed)
N_SUGGESTIONS = 3         # "What's next?" shows this many likely activities
PWA_URL = "https://latifalfayach.github.io/iob-behavior-graph/"

STORY_VERBS = {
    "wake_up": "You woke up", "phone_bed": "Checked your phone",
    "bathroom": "Bathroom / hygiene", "shower": "Took a shower",
    "exercise": "Exercise / stretching", "dressed": "Got dressed",
    "coffee": "Coffee / tea", "breakfast": "Had breakfast",
    "news_social": "News / social media", "prep_bag": "Prepared your bag",
    "meditate": "Meditation / reading", "leave_home": "Left home",
    "commute": "Commute", "arrive_work": "Arrived at work",
}

st.set_page_config(page_title="Morning Companion", page_icon="🌅")

# Warm + calm + minimal styling
st.markdown("""<style>
.stApp { background-color:#FAF7F2; }
div.stButton > button {
    width:100%; border-radius:14px; border:1px solid #EFE7DA;
    background:#FFFFFF; padding:0.8rem 1rem; font-size:1.05rem; text-align:left;
}
div.stButton > button:hover { border-color:#F0A840; background:#FFF8EE; }
.card {
    background:#FFFFFF; border-radius:18px; padding:26px; text-align:center;
    border:1px solid #EFE7DA; box-shadow:0 2px 10px rgba(0,0,0,.05); margin:14px 0;
}
.journey { color:#6B6259; line-height:1.9; }
</style>""", unsafe_allow_html=True)

# Quiet refresh so elapsed time and the check-in update while the page stays open
st_autorefresh(interval=AUTOREFRESH_MS, key="quiet_tick")

now_utc = datetime.now(timezone.utc)
today = date.today().isoformat()
day_type = "weekday" if date.today().weekday() < 5 else "weekend"


def parse_ts(value):
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


# ---------------- participant (auto-ID, no personal info) ----------------
try:
    users = sheets_client.load_users()
except Exception as e:
    st.error(f"Could not connect to Google Sheets: {e}")
    st.stop()

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if st.session_state.user_id is None:
    st.markdown("## ☀️ Welcome to Morning Companion")
    choice = st.radio("Are you…", ["A new participant", "A returning participant"])
    if choice == "A new participant":
        st.caption("We'll create an anonymous ID for you — no name, no personal info.")
        if st.button("✨ Create my ID", use_container_width=True):
            st.session_state.user_id = sheets_client.create_user()
            st.session_state.just_created = True
            st.rerun()
    else:
        if not users:
            st.info("No participants yet — choose 'A new participant'.")
        else:
            sel = st.selectbox("Pick your ID", users)
            if st.button("Continue", use_container_width=True):
                st.session_state.user_id = sel
                st.rerun()
    st.stop()

user_id = st.session_state.user_id
st.caption(f"Your anonymous ID: **{user_id}**")

# One-time setup screen: offer reminder setup with the ID pre-linked
if st.session_state.get("just_created"):
    st.markdown(f"## 🎉 Welcome, {user_id}!")
    st.write("Your anonymous ID is ready. One last **optional** step — "
             "get a gentle reminder if your morning goes quiet:")
    st.link_button("🔔 Enable gentle reminders",
                   f"{PWA_URL}?id={user_id}",
                   use_container_width=True)
    st.caption("📱 iPhone: on the page that opens, tap **Share → Add to Home Screen** first, "
               "then tap Enable. Your ID is already filled in — no typing needed.")
    if st.button("🌅 Continue to the app", type="primary", use_container_width=True):
        st.session_state.just_created = False
        st.rerun()
    st.stop()

with st.expander("🔔 Not getting reminders yet?"):
    st.link_button("Enable gentle reminders",
                   f"{PWA_URL}?id={user_id}",
                   use_container_width=True)

# Load today's data once per participant (survives page refreshes)
if st.session_state.get("loaded_for") != user_id:
    st.session_state.chain = sheets_client.load_today_events(user_id)
    st.session_state.session = sheets_client.load_today_session(user_id)
    st.session_state.loaded_for = user_id

chain = st.session_state.chain
session = st.session_state.session


# ---------------- actions ----------------
def log_activity(activity_id):
    ts = datetime.now(timezone.utc)
    local = datetime.now().astimezone()
    if chain:  # ignore double tap of the same activity within 60 s
        prev = parse_ts(chain[-1].get("ts_utc"))
        if chain[-1].get("activity_id") == activity_id and prev \
                and (ts - prev).total_seconds() < 60:
            return
    event = {
        "event_id": str(uuid.uuid4()),
        "user_id": user_id,
        "session_date": today,
        "seq_index": len(chain) + 1,
        "activity_id": activity_id,
        "ts_utc": ts.isoformat(timespec="seconds"),
        "local_time": local.strftime("%H:%M:%S"),
        "day_type": day_type,
        "device": "web",
    }
    sheets_client.append_event(event)
    chain.append(event)


def finish_morning():
    if chain and chain[-1].get("activity_id") != "arrive_work":
        log_activity("arrive_work")
    if len(chain) < 3:
        st.toast("Log a few activities first 🌱")
        return
    t0, t1 = parse_ts(chain[0]["ts_utc"]), parse_ts(chain[-1]["ts_utc"])
    row = {
        "session_id": f"{user_id}_{today}",
        "user_id": user_id,
        "session_date": today,
        "n_events": len(chain),
        "chain": ">".join(e["activity_id"] for e in chain),
        "duration_min": round((t1 - t0).total_seconds() / 60, 1) if t0 and t1 else "",
        "complete": True,
    }
    sheets_client.append_session(row)
    st.session_state.session = row


def activity_grid(items, key_prefix):
    cols = st.columns(2)
    for i, act in enumerate(items):
        with cols[i % 2]:
            st.button(f"{act['icon']}  {act['label']}", key=f"{key_prefix}_{act['id']}",
                      use_container_width=True, on_click=log_activity, args=(act["id"],))


# ================= SCREENS =================
if session:
    # ---------- Morning story ----------
    st.markdown(f"## ☀️ Good morning, {user_id}")
    st.caption(date.today().strftime("%A · %B %d"))
    st.markdown("### Your morning story")
    for e in chain:
        a = ACTIVITY_BY_ID.get(e["activity_id"], {"icon": "•"})
        t = str(e.get("local_time", ""))[:5]
        st.markdown(f"**{t}** — {a['icon']} {STORY_VERBS.get(e['activity_id'], e['activity_id'])}")
        st.markdown("<div style='margin-left:12px;color:#C9BBA6'>↓</div>",
                    unsafe_allow_html=True)
    try:
        dm = float(session.get("duration_min", 0))
        dur = f"{int(dm // 60)}h {int(dm % 60):02d}m" if dm >= 60 else f"{int(dm)} min"
        st.markdown(f"**Morning duration:** {dur}")
    except Exception:
        pass
    st.success("✨ Thanks for logging! See you tomorrow.")

elif not chain:
    # ---------- Welcome ----------
    st.markdown(f"## ☀️ Good morning, {user_id}")
    st.caption(date.today().strftime("%A · %B %d"))
    st.markdown("#### Your morning is about to begin")
    st.button("🌅  I just woke up", use_container_width=True,
              on_click=log_activity, args=("wake_up",))
    with st.expander("Already up? Log what you're doing"):
        activity_grid(ACTIVITIES, "welcome")

else:
    # ---------- Morning in progress ----------
    current = chain[-1]
    cur = ACTIVITY_BY_ID[current["activity_id"]]
    start = parse_ts(current.get("ts_utc"))
    elapsed = int((now_utc - start).total_seconds() // 60) if start else None
    since_txt = f"since {str(current.get('local_time', ''))[:5]}"
    if elapsed is not None:
        since_txt += f" · {elapsed} min" if elapsed < 60 else f" · {elapsed//60}h {elapsed%60:02d}m"

    st.markdown(f"## ☀️ Good morning, {user_id}")
    st.caption(f"{date.today().strftime('%A · %B %d')} — your morning is in progress")

    st.markdown(f"""<div class="card">
        <div style="font-size:2.6rem">{cur['icon']}</div>
        <div style="font-size:1.3rem;font-weight:600">{cur['label']}</div>
        <div style="color:#8A7F72">{since_txt}</div>
    </div>""", unsafe_allow_html=True)

    # Gentle inactivity check-in (only while the page is open)
    if elapsed is not None and elapsed >= INACTIVITY_MIN:
        st.info("☀️ Quick check-in — what are you up to?")

    # What's next? — a few likely activities, not the whole taxonomy
    done_ids = {e["activity_id"] for e in chain}
    remaining = [a for a in ACTIVITIES if a["id"] not in done_ids and a["id"] != "wake_up"]
    st.markdown("#### What's next?")
    for act in remaining[:N_SUGGESTIONS]:
        st.button(f"{act['icon']}  {act['label']}", key=f"next_{act['id']}",
                  use_container_width=True, on_click=log_activity, args=(act["id"],))
    with st.expander("＋ Something else"):
        activity_grid(remaining[N_SUGGESTIONS:], "more")

    st.button("🏢  I'm at work", type="primary",
              use_container_width=True, on_click=finish_morning)

    # Journey
    st.markdown("---")
    st.markdown("#### Your morning 🌅")
    lines = []
    for i, e in enumerate(chain):
        a = ACTIVITY_BY_ID[e["activity_id"]]
        marker = "◉" if i == len(chain) - 1 else "●"
        now_tag = "  ← now" if i == len(chain) - 1 else ""
        lines.append(f"{marker} {a['icon']} {a['label']} · {str(e.get('local_time', ''))[:5]}{now_tag}")
    for a in remaining[:3]:
        lines.append(f"○ {a['icon']} {a['label']}")
    st.markdown("<div class='journey'>" + "<br>".join(lines) + "</div>",
                unsafe_allow_html=True)

    # Neutral progress — position along the routine, never judged
    order = [a["id"] for a in ACTIVITIES]
    furthest = max(order.index(e["activity_id"]) for e in chain)
    st.progress(furthest / (len(order) - 1))
    st.caption("You're getting there ☀️")