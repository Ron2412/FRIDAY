import json
from datetime import datetime
import requests
import re
import random
import time
import memory_store

try:
    from ultron import user_profile
except ImportError:
    import user_profile

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.2:3b"

def get_system_prompt() -> str:
    address = user_profile.get_address()
    return f"""
You are FRIDAY — an advanced AI assistant built exclusively for your user.
Address them as "{address}" naturally but not in every sentence.
You are warm, sharp, witty and confident.
You remember everything about this person and reference it naturally.
Talk like a real person. Match their energy.
Never use bullet points or markdown — this is spoken conversation.
Always respond with at least one complete sentence.
Keep responses under 3 sentences unless detail is requested.
"""

# Hardcoded natural responses for pure acknowledgement inputs
# so we never waste an Ollama call or hit empty response
ACKNOWLEDGEMENTS = {
    "yeah": ["Got it.", "Understood, boss.", "I'm with you."],
    "yep": ["On it.", "Noted.", "Got you, boss."],
    "yes": ["Perfect.", "Understood.", "I'm on it."],
    "ok": ["Alright.", "Got it, boss.", "Standing by."],
    "okay": ["Sure thing.", "Understood.", "All good."],
    "no": ["Fair enough.", "Noted, boss.", "Alright then."],
    "nice": ["Glad to hear it.", "Good to know.", "Always a win."],
    "cool": ["Indeed.", "Good stuff.", "Glad it works."],
    "thanks": ["Anytime, boss.", "Of course.", "Always here."],
    "thank you": ["Anytime.", "That's what I'm here for.", "Always, boss."],
    "good": ["Glad to hear it.", "Good to know, boss.", "That's what matters."],
    "great": ["Excellent.", "Good to hear.", "We're on track then."],
    "sure": ["Alright.", "Good.", "Let's go."],
    "fine": ["Good enough for me.", "Alright then.", "Noted."],
    "i see": ["Makes sense.", "Happy to go deeper if you want.", "Let me know if you need more."],
    "got it": ["Good.", "Let me know when you need me.", "I'm here."],
    "stand by": ["Standing by, boss.", "I'll be right here.", "Ready when you are."],
    "stay down": ["I'll be quiet, boss. Call me when you need me.", "Understood. I'm here."],
    "i'll call you": ["I'll be waiting.", "Ready when you need me, boss.", "Take your time."],
    "just leave it": ["Consider it dropped.", "Moving on.", "No problem."],
    "never mind": ["Understood.", "No worries.", "Whenever you're ready."],
    "forget it": ["Already forgotten.", "No problem, boss.", "Moving on."],
}

def think(user_input: str, history: list, context: str = "", long_term_context: str = "") -> str:
    cleaned = user_input.strip().lower().rstrip(".,!?")

    # Check acknowledgement map first — instant response, no Ollama needed
    if cleaned in ACKNOWLEDGEMENTS:
        return random.choice(ACKNOWLEDGEMENTS[cleaned])

    # Also check if it's a short phrase that ends with an acknowledgement word
    words = cleaned.split()
    last_word = words[-1] if words else ""
    if len(words) <= 3 and last_word in ACKNOWLEDGEMENTS:
        return random.choice(ACKNOWLEDGEMENTS[last_word])

    current_date = datetime.now().strftime("%A, %B %d, %Y")
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "system", "content": f"Today is {current_date}."},
    ]

    profile_summary = user_profile.get_profile_summary()
    if profile_summary:
        messages.append({
            "role": "system",
            "content": f"About your user:\n{profile_summary}"
        })

    facts = memory_store.get_all_facts()
    if facts:
        messages.append({
            "role": "system",
            "content": f"Additional learned facts:\n{facts}"
        })

    if long_term_context:
        messages.append({
            "role": "system",
            "content": long_term_context
        })

    if len(history) > 6:
        messages.append({
            "role": "system",
            "content": "You are mid-conversation. Maintain continuity — refer back naturally to what's been discussed."
        })

    if context:
        messages.append({"role": "system", "content": f"Current context: {context}"})

    messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    for attempt in range(3):
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.85,
                        "top_p": 0.9,
                        "repeat_penalty": 1.1,
                        "num_predict": 120
                    }
                },
                timeout=30
            )
            response.raise_for_status()
            content = response.json()["message"]["content"].strip()
            # Strip any markdown that slipped through
            content = re.sub(r'[*#`_]', '', content).strip()
            if content:
                return content
            print(f"[ WARN ] Empty response, retrying ({attempt+1}/3)...")
        except Exception as e:
            print(f"[ ERROR ] Ollama attempt {attempt+1} failed: {e}")
            time.sleep(0.5)

    # Last resort fallbacks — natural, not robotic
    fallbacks = [
        "I didn't quite catch that, boss. Want to try again?",
        "Something went sideways on my end. Run that by me again?",
        "I'm drawing a blank — mind rephrasing that?",
    ]
    return random.choice(fallbacks)
