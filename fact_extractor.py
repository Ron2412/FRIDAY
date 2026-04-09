import re

try:
    from ultron import user_profile as prof
except ImportError:
    import user_profile as prof

# Patterns that suggest the user is sharing personal info
FACT_PATTERNS = [
    (r"my name is (\w+)", "user_name"),
    (r"i(?:'m| am) (\w+)", "user_name"),
    (r"call me (\w+)", "user_name"),
    (r"i(?:'m| am) from ([a-zA-Z\s]+)", "user_location"),
    (r"i live in ([a-zA-Z\s]+)", "user_location"),
    (r"i(?:'m| am) (\d+) years old", "user_age"),
    (r"i work (?:at|for|as) ([a-zA-Z\s]+)", "user_job"),
    (r"i(?:'m| am) a(?:n)? ([a-zA-Z\s]+)", "user_role"),
    (r"i(?:'m| am) studying ([a-zA-Z\s]+)", "user_study"),
    (r"i love ([a-zA-Z\s]+)", "user_interest"),
    (r"i hate ([a-zA-Z\s]+)", "user_dislike"),
    (r"my (?:favourite|favorite) ([a-zA-Z]+) is ([a-zA-Z\s]+)", "user_preference"),
    (r"i prefer ([a-zA-Z\s]+)", "user_preference"),
    (r"i usually ([a-zA-Z\s]+)", "user_habit"),
    (r"wake up at (\d+(?::\d+)?(?:am|pm)?)", "user_wake_time"),
    (r"i sleep at (\d+(?::\d+)?(?:am|pm)?)", "user_sleep_time"),
]

FACT_TO_PROFILE = {
    "user_name": "name",
    "user_location": "location",
    "user_age": "age",
    "user_job": "occupation",
    "user_wake_time": "wake_time",
    "user_sleep_time": "sleep_time",
    "user_interest": "interests",
    "user_dislike": "dislikes",
}

def extract_facts(text: str) -> list[tuple[str, str]]:
    """Extract key-value facts from user speech. Returns list of (key, value) tuples."""
    found = []
    text_lower = text.lower().strip()
    for pattern, key in FACT_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            value = match.group(1).strip()
            if len(value) > 1:
                found.append((key, value))
    return found


def extract_and_save(text: str):
    """Extract facts and immediately persist relevant profile fields."""
    facts = extract_facts(text)
    for key, value in facts:
        profile_key = FACT_TO_PROFILE.get(key)
        if profile_key:
            prof.update(profile_key, value)
            print(f"[ FRIDAY ] Profile updated: {profile_key} = {value}")
    return facts
