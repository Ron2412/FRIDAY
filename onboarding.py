try:
    from ultron import user_profile, voice, ears
except ImportError:
    import user_profile
    import voice
    import ears


def run_if_needed() -> bool:
    """Returns True if onboarding was run, False if skipped."""
    p = user_profile.load()
    if p.get("name"):
        return False

    voice.speak("Before we begin, I'd love to know your name. What should I call you?")

    try:
        ears.calibrate()
        response = ears.listen()
        if response:
            # Extract just the name — take last word if they said "my name is X"
            words = response.strip().split()
            name = words[-1].rstrip(".,!?").capitalize()
            user_profile.update("name", name)
            user_profile.update("preferred_name", name)
            voice.speak(
                f"Great to meet you, {name}. "
                f"I'm FRIDAY — I'll remember everything we talk about. "
                f"You can tell me about yourself naturally and I'll learn as we go."
            )
            return True
    except Exception as e:
        print(f"[ FRIDAY ] Onboarding skipped: {e}")

    return False
