"""Closed 15-activity taxonomy for the morning-routine domain."""

ACTIVITIES = [
    {"id": "wake_up",     "label": "Wake up",                 "icon": "🌅", "category": "start"},
    {"id": "phone_bed",   "label": "Phone in bed",            "icon": "📱", "category": "start"},
    {"id": "bathroom",    "label": "Bathroom / hygiene",      "icon": "🚿", "category": "hygiene"},
    {"id": "shower",      "label": "Shower",                  "icon": "🛁", "category": "hygiene"},
    {"id": "exercise",    "label": "Exercise / stretching",   "icon": "🤸", "category": "body"},
    {"id": "dressed",     "label": "Get dressed",             "icon": "👕", "category": "prepare"},
    {"id": "coffee",      "label": "Coffee / tea",            "icon": "☕", "category": "food"},
    {"id": "breakfast",   "label": "Breakfast",               "icon": "🍳", "category": "food"},
    {"id": "news_social", "label": "News / social media",     "icon": "📰", "category": "mind"},
    {"id": "prep_bag",    "label": "Prepare bag",             "icon": "🎒", "category": "prepare"},
    {"id": "meditate",    "label": "Meditation / reading",    "icon": "🧘", "category": "mind"},
    {"id": "leave_home",  "label": "Leave home",              "icon": "🚪", "category": "transition"},
    {"id": "commute",     "label": "Commute",                 "icon": "🚌", "category": "transition"},
    {"id": "arrive_work", "label": "Arrive at work",          "icon": "🏢", "category": "end"},
    {"id": "staying_home","label": "Staying home today",      "icon": "🏠", "category": "end"},
]

ACTIVITY_BY_ID = {a["id"]: a for a in ACTIVITIES}
