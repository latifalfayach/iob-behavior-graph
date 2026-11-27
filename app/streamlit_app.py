"""Morning Companion — calm, companion-style UI with device-linked anonymous IDs."""
import re
import time
import uuid
from datetime import datetime, timezone, date

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from streamlit_local_storage import LocalStorage

from activities import ACTIVITIES, ACTIVITY_BY_ID
import sheets_client

# ---------------- config ----------------
INACTIVITY_MIN = 12       # gentle in-page check-in after this many quiet minutes
AUTOREFRESH_MS = 60_000   # page quietly refreshes once a minute (no push needed)
N_SUGGESTIONS = 3         # "What's next?" shows this many likely activities
APP_URL = "https://iob-behavior-graph-ehfisophxqtinrgvxsxryr.streamlit.app/"            # <-- your deployed app URL
PWA_URL = "https://latifalfayach.github.io/iob-behavior-graph/pwa/"  # <-- your GitHub Pages URL

STORY_VERBS = {
    "wake_up": "You woke up", "phone_bed": "Checked your phone",
    "bathroom": "Bathroom / hygiene", "shower": "Took a shower",
    "exercise": "Exercise / stretching", "dressed": "Got dressed",
    "coffee": "Coffee / tea", "breakfast": "Had breakfast",
    "news_social": "News / social media", "prep_bag": "Prepared your bag",
    "meditate": "Meditation / reading", "leave_home": "Left home",
    "commute": "Commute", "arrive_work": "Arrived at work",
    "staying_home": "Stayed home today",
}

END_IDS = {a["id"] for a in ACTIVITIES if a["category"] == "end"}

st.set_page_config(page_title="Morning Companion", page_icon="🌅")

# Warm + calm + minimal styling
st.markdown("""<style>
.stApp { background-color:#FAF7F2; }

/* default buttons: white cards */
div.stButton > button {
    width:100%; border-radius:14px; border:1px solid #EFE7DA;
    background:#FFFFFF; color:#3B342C;
    padding:0.8rem 1rem; font-size:1.05rem; text-align:left;
}
div.stButton > button:hover { border-color:#F0A840; background:#FFF8EE; color:#3B342C; }

/* primary buttons: warm orange with white text */
div.stButton > button[kind="primary"],
div.stButton > button[data-testid="stBaseButton-primary"] {
    background:#F0A840; color:#FFFFFF; border:none; font-weight:600;
}
div.stButton > button[kind="primary"]:hover,
div.stButton > button[data-testid="stBaseButton-primary"]:hover {
    background:#D68A20; color:#FFFFFF; border:none;
}
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


# ============ participant (device-linked ID, no public list) ============
try:
    users = sheets_client.load_users()
except Exception as e:
    st.error(f"Could not connect to Google Sheets: {e}")
    st.stop()

localS = LocalStorage()
stored_id = (localS.getItem("participant_id") or "").strip().upper()

if "user_id" not in st.session_state:
    st.session_state.user_id = None

# Admin/testing escape hatch: ?reset=1 unlinks this device
if st.query_params.get("reset") == "1":
    localS.setItem("participant_id", "")
    st.session_state.user_id = None
    st.query_params.clear()
    st.rerun()

# Sanitize ?id= — anything that isn't a real ID format ({USER_ID}, garbage) is dropped
qp_id = (st.query_params.get("id", "") or "").strip().upper()
if qp_id and not re.fullmatch(r"U\d{3}", qp_id):
    qp_id = ""
    st.query_params.clear()

# A personal link for a DIFFERENT ID is rejected on a linked device
if qp_id and stored_id and qp_id != stored_id:
    st.warning(f"🔒 This device is already linked to **{stored_id}** — "
               f"the ID **{qp_id}** isn't associated with this device.")
    qp_id = ""

# Loading gate: wait for browser storage before offering any registration option,
# so a linked device never sees "Create my ID", even for a moment.
if st.session_state.user_id is None and not stored_id and not qp_id:
    checks = st.session_state.get("ls_checks", 0)
    if checks < 3:
        st.session_state.ls_checks = checks + 1
        st.info("Loading your profile…")
        time.sleep(0.5)
        st.rerun()

# 1) Device already linked -> automatic login
if st.session_state.user_id is None and stored_id:
    if stored_id in users:
        st.session_state.user_id = stored_id
        st.rerun()
    else:
        st.error(f"Your saved ID {stored_id} was not found — please contact the researcher.")

# 2) Personal link on an unlinked device -> login + link this device
if st.session_state.user_id is None and qp_id:
    if qp_id in users:
        st.session_state.user_id = qp_id
        localS.setItem("participant_id", qp_id)
        st.rerun()
    else:
        st.query_params.clear()
        st.warning(f"The ID **{qp_id}** doesn't exist (old link?) — "
                   "log in or create a new ID below.")

# 3) First-ever visit on this device: create a new ID or type an existing one
if st.session_state.user_id is None:
    st.markdown("## ☀️ Welcome to Morning Companion")
    choice = st.radio("Are you…", ["A new participant", "A returning participant"])
    if choice == "A new participant":
        st.caption("We'll create an anonymous ID for you — no name, no personal info.")
        if st.session_state.get("creating"):
            st.info("Creating your ID…")
        elif st.button("✨ Create my ID", use_container_width=True):
            st.session_state.creating = True          # lock BEFORE the Sheet call
            new_id = sheets_client.create_user()
            localS.setItem("participant_id", new_id)
            st.session_state.user_id = new_id
            st.session_state.just_created = True
            st.session_state.creating = False
            st.rerun()
    else:
        if not users:
            st.info("No participants yet — choose 'A new participant'.")
        else:
            typed = st.text_input("Your ID", placeholder="e.g. U001").strip().upper()
            if st.button("Continue", use_container_width=True):
                if typed in users:
                    localS.setItem("participant_id", typed)
                    st.session_state.user_id = typed
                    st.rerun()
                else:
                    st.error("ID not found — check the spelling, or choose 'A new participant'.")
    st.stop()

user_id = st.session_state.user_id
st.caption(f"🔒 This device is linked to **{user_id}**")
# Keep the ID in the URL so any bookmark / home-screen icon / reopened tab
# always carries the identity — no dependence on browser storage.
if st.query_params.get("id") != user_id:
    st.query_params["id"] = user_id

# One-time setup screen after ID creation
if st.session_state.get("just_created"):
    st.markdown(f"## 🎉 Welcome, {user_id}!")
    st.markdown("### 🔗 Your personal link")
    st.write("Bookmark this on your phone — it opens the app already logged in as you:")
    st.code(f"{APP_URL}?id={user_id}")
    st.write("One last **optional** step — get a gentle reminder if your morning goes quiet:")
    st.link_button("🔔 Enable gentle reminders",
                   f"{PWA_URL}?id={user_id}",
                   use_container_width=True)
    st.caption("📱 iPhone: on the page that opens, tap **Share → Add to Home Screen** first, "
               "then tap Enable. Your ID is already filled in — no typing needed.")
    if st.button("🌅 Continue to the app",type="primary", use_container_width=True):
        st.session_state.just_created = False
        st.rerun()
    st.stop()

# Returning participants who never set up reminders
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
        "source": "live",
    }
    sheets_client.append_event(event)
    chain.append(event)


def finish_morning(end_activity):
    if chain and chain[-1].get("activity_id") not in END_IDS:
        log_activity(end_activity)
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
        "closed_by": "user",
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
mode = st.session_state.get("mode")

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

elif mode == "recap":
    # ---------- Quick recap (also reachable from live mode) ----------
    from datetime import time as dtime

    st.markdown(f"## ⚡ Quick recap, {user_id}")
    st.caption("Tap your activities **in the order they happened**. Tap again to remove.")

    if "recall" not in st.session_state:
        st.session_state.recall = []
    if "recap_anchors" not in st.session_state:
        st.session_state.recap_anchors = {}

    def toggle(act_id):
        if act_id in st.session_state.recall:
            st.session_state.recall.remove(act_id)
        else:
            st.session_state.recall.append(act_id)

    # the chain being built
    if st.session_state.recall:
        parts = [f"{ACTIVITY_BY_ID[a]['icon']} {ACTIVITY_BY_ID[a]['label']}"
                 for a in st.session_state.recall]
        st.markdown(" → ".join(parts))
    else:
        st.info("Nothing selected yet — start with what you did first.")

    # activity chips (end activities are chosen separately below)
    core = [a for a in ACTIVITIES if a["category"] != "end"]
    cols = st.columns(2)
    for i, act in enumerate(core):
        selected = act["id"] in st.session_state.recall
        with cols[i % 2]:
            st.button(
                f"{'✓ ' if selected else ''}{act['icon']} {act['label']}",
                key=f"recall_{act['id']}",
                type="primary" if selected else "secondary",
                use_container_width=True,
                on_click=toggle, args=(act["id"],),
            )

    st.markdown("---")
    wake_t = st.time_input("🌅 You woke up around…", dtime(7, 0))
    end_choice = st.radio("Your morning ended with…",
                          ["🏢 Arrived at work", "🏠 Stayed home"],
                          horizontal=True)
    end_t = st.time_input("…around", dtime(9, 0))

    if st.button("✅ Save my morning", type="primary", use_container_width=True):
        recall = list(st.session_state.recall)
        if "wake_up" not in recall:
            recall = ["wake_up"] + recall          # every morning starts here
        if len(recall) < 3:
            st.warning("Pick at least 3 activities 🌱")
            st.stop()
        end_id = "arrive_work" if "work" in end_choice else "staying_home"
        full = recall + [end_id]
        base = datetime.combine(date.today(), wake_t)
        end_dt = datetime.combine(date.today(), end_t)
        anchors = dict(st.session_state.get("recap_anchors", {}))

        # Timestamps: live-logged activities keep their real time (anchors);
        # newly added ones are interpolated between surrounding anchors.
        anchor_points = {}
        for pos, act_id in enumerate(full):
            if act_id in anchors:
                anchor_points[pos] = datetime.fromisoformat(anchors[act_id])
        anchor_points.setdefault(0, base)                  # wake anchor
        anchor_points.setdefault(len(full) - 1, end_dt)    # end anchor

        ts_for = {}
        marks = sorted(anchor_points)
        for a, b in zip(marks, marks[1:]):
            step = (anchor_points[b] - anchor_points[a]) / (b - a)
            for pos in range(a, b + 1):
                ts_for[pos] = anchor_points[a] + step * (pos - a)

        # Rewrite today's events atomically: delete old, insert merged
        sheets_client.delete_today_events(user_id)
        events = []
        for i, act_id in enumerate(full):
            ts = ts_for[i]
            events.append({
                "event_id": str(uuid.uuid4()),
                "user_id": user_id,
                "session_date": today,
                "seq_index": i + 1,
                "activity_id": act_id,
                "ts_utc": ts.isoformat(timespec="seconds") + "+00:00"
                          if ts.tzinfo is None else ts.isoformat(timespec="seconds"),
                "local_time": ts.strftime("%H:%M:%S"),
                "day_type": day_type,
                "device": "web",
                "source": "live" if act_id in anchors else "recall",
            })
            sheets_client.append_event(events[-1])

        duration = (ts_for[len(full) - 1] - ts_for[0]).total_seconds() / 60
        row = {
            "session_id": f"{user_id}_{today}",
            "user_id": user_id,
            "session_date": today,
            "n_events": len(events),
            "chain": ">".join(full),
            "duration_min": round(duration, 1),
            "complete": True,
            "closed_by": "user",
        }
        sheets_client.append_session(row)
        st.session_state.chain = events
        st.session_state.session = row
        st.session_state.recall = []
        st.session_state.recap_anchors = {}
        st.session_state.mode = None
        st.rerun()

elif chain:
    # ---------- Live mode in progress ----------
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

    if elapsed is not None and elapsed >= INACTIVITY_MIN:
        st.info("☀️ Quick check-in — what are you up to?")

    done_ids = {e["activity_id"] for e in chain}
    remaining = [a for a in ACTIVITIES
                 if a["id"] not in done_ids
                 and a["id"] != "wake_up"
                 and a["category"] != "end"]
    st.markdown("#### What's next?")
    for act in remaining[:N_SUGGESTIONS]:
        st.button(f"{act['icon']}  {act['label']}", key=f"next_{act['id']}",
                  use_container_width=True, on_click=log_activity, args=(act["id"],))
    with st.expander("＋ Something else"):
        activity_grid(remaining[N_SUGGESTIONS:], "more")

    end_col1, end_col2 = st.columns(2)
    with end_col1:
        st.button("🏢  I'm at work", type="primary", use_container_width=True,
                  on_click=finish_morning, args=("arrive_work",))
    with end_col2:
        st.button("🏠  Staying home today", use_container_width=True,
                  on_click=finish_morning, args=("staying_home",))

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

    order = [a["id"] for a in ACTIVITIES]
    furthest = max(order.index(e["activity_id"]) for e in chain)
    st.progress(furthest / (len(order) - 1))
    st.caption("You're getting there ☀️")

    # switch to recap, keeping live timestamps as anchors
    with st.expander("✏️ I forgot something — fix my morning"):
        st.caption("Switch to recap: your logged times stay exact, "
                   "you just add what you forgot.")
        if st.button("Switch to recap mode", use_container_width=True):
            st.session_state.mode = "recap"
            st.session_state.recall = [e["activity_id"] for e in chain
                                       if e["activity_id"] not in END_IDS]
            st.session_state.recap_anchors = {
                e["activity_id"]: str(e["ts_utc"]) for e in chain}
            st.rerun()

else:
    # ---------- No data yet today: choose the mode ----------
    if mode is None:
        st.markdown(f"## ☀️ Good morning, {user_id}")
        st.caption(date.today().strftime("%A · %B %d"))
        st.markdown("#### How do you want to log today?")
        if st.button("⚡  Quick recap — 30 seconds", type="primary",
                     use_container_width=True):
            st.session_state.mode = "recap"
            st.session_state.recall = []
            st.session_state.recap_anchors = {}
            st.rerun()
        st.caption("Tell me what you did this morning, in order. No timers, no pressure.")
        if st.button("🌅  Log live as I go", use_container_width=True):
            st.session_state.mode = "live"
            st.rerun()
        st.caption("Tap each activity as it happens — precise timestamps.")
    else:  # mode == "live"
        st.markdown(f"## ☀️ Good morning, {user_id}")
        st.caption(date.today().strftime("%A · %B %d"))
        st.markdown("#### Your morning is about to begin")
        st.button("🌅  I just woke up", use_container_width=True,
                  on_click=log_activity, args=("wake_up",))
        with st.expander("Already up? Log what you're doing"):
            activity_grid(ACTIVITIES, "welcome")