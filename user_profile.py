import json
from copy import deepcopy
from pathlib import Path
from datetime import datetime

PROFILE_PATH = Path(__file__).parent / "data" / "profile.json"
PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_PROFILE = {
    "name": None,
    "preferred_name": None,
    "location": None,
    "timezone": None,
    "age": None,
    "occupation": None,
    "wake_time": None,
    "sleep_time": None,
    "interests": [],
    "dislikes": [],
    "language": "en",
    "response_style": "balanced",
    "created_at": None,
    "last_seen": None,
    "total_sessions": 0,
    "total_exchanges": 0,
    "notes": []
}

def load() -> dict:
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH, "r") as f:
            data = json.load(f)
            merged = {**deepcopy(DEFAULT_PROFILE), **data}
            return merged
    profile = deepcopy(DEFAULT_PROFILE)
    profile["created_at"] = datetime.now().isoformat()
    save(profile)
    return profile

def save(profile: dict):
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)

def update(key: str, value):
    profile = load()
    if key == "interests" and isinstance(profile["interests"], list):
        if value not in profile["interests"]:
            profile["interests"].append(value)
    elif key == "dislikes" and isinstance(profile["dislikes"], list):
        if value not in profile["dislikes"]:
            profile["dislikes"].append(value)
    elif key == "notes" and isinstance(profile["notes"], list):
        profile["notes"].append({
            "note": value,
            "added": datetime.now().isoformat()
        })
    else:
        profile[key] = value
        if key == "name" and not profile.get("preferred_name"):
            profile["preferred_name"] = value
    save(profile)

def record_session():
    profile = load()
    profile["last_seen"] = datetime.now().isoformat()
    profile["total_sessions"] = profile.get("total_sessions", 0) + 1
    save(profile)

def record_exchange():
    profile = load()
    profile["total_exchanges"] = profile.get("total_exchanges", 0) + 1
    save(profile)

def get_address() -> str:
    """Returns what FRIDAY should call the user."""
    profile = load()
    name = profile.get("preferred_name") or profile.get("name")
    return name if name else "boss"

def get_profile_summary() -> str:
    """Returns a natural language summary of the profile for injection into system prompt."""
    profile = load()
    lines = []
    name = profile.get("preferred_name") or profile.get("name")
    if name:
        lines.append(f"User's name is {name}.")
    if profile.get("location"):
        lines.append(f"They are based in {profile['location']}.")
    if profile.get("occupation"):
        lines.append(f"They work as a {profile['occupation']}.")
    if profile.get("age"):
        lines.append(f"They are {profile['age']} years old.")
    if profile.get("wake_time"):
        lines.append(f"They typically wake up at {profile['wake_time']}.")
    if profile.get("interests"):
        lines.append(f"Their interests include: {', '.join(profile['interests'])}.")
    if profile.get("dislikes"):
        lines.append(f"They dislike: {', '.join(profile['dislikes'])}.")
    if profile.get("response_style") == "concise":
        lines.append("They prefer very short, direct answers.")
    elif profile.get("response_style") == "detailed":
        lines.append("They enjoy detailed, thorough explanations.")
    if profile.get("notes"):
        recent_notes = profile["notes"][-3:]
        for n in recent_notes:
            lines.append(f"Note: {n['note']}")
    return "\n".join(lines) if lines else ""

def get_greeting() -> str:
    """Generate a personalised startup greeting based on profile and time of day."""
    profile = load()
    name = profile.get("preferred_name") or profile.get("name")
    address = name if name else "boss"
    hour = datetime.now().hour
    sessions = profile.get("total_sessions", 0)

    if hour < 12:
        time_greeting = "Good morning"
    elif hour < 17:
        time_greeting = "Good afternoon"
    elif hour < 21:
        time_greeting = "Good evening"
    else:
        time_greeting = "Hey"

    if sessions == 0:
        return f"Hello. I'm FRIDAY, your personal AI assistant. What should I call you?"
    elif sessions == 1:
        return f"{time_greeting}, {address}."
    elif sessions < 10:
        return f"{time_greeting}, {address}. FRIDAY online."
    else:
        return f"{time_greeting}, {address}."
