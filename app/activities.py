# Fixed activity taxonomy (v1) — must match the 'activities' tab in the Sheet
ACTIVITIES = [
    {"id": "wake_up",     "label": "Wake up",                "icon": "⏰", "category": "start"},
    {"id": "phone_bed",   "label": "Check phone in bed",     "icon": "📱", "category": "digital"},
    {"id": "bathroom",    "label": "Bathroom / hygiene",     "icon": "🪥", "category": "hygiene"},
    {"id": "shower",      "label": "Shower",                 "icon": "🚿", "category": "hygiene"},
    {"id": "exercise",    "label": "Exercise / stretching",  "icon": "🏃", "category": "health"},
    {"id": "dressed",     "label": "Get dressed",            "icon": "👕", "category": "routine"},
    {"id": "coffee",      "label": "Make coffee / tea",      "icon": "☕", "category": "food"},
    {"id": "breakfast",   "label": "Eat breakfast",          "icon": "🍳", "category": "food"},
    {"id": "news_social", "label": "News / social media",    "icon": "📰", "category": "digital"},
    {"id": "prep_bag",    "label": "Prepare bag / keys",     "icon": "🎒", "category": "routine"},
    {"id": "meditate",    "label": "Meditate / read",        "icon": "🧘", "category": "health"},
    {"id": "leave_home",  "label": "Leave home",             "icon": "🚪", "category": "transition"},
    {"id": "commute",     "label": "Commute",                "icon": "🚌", "category": "transition"},
    {"id": "arrive_work", "label": "Arrive at work/school",  "icon": "🏢", "category": "end"},
]

ACTIVITY_BY_ID = {a["id"]: a for a in ACTIVITIES}