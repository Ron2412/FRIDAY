import json
import requests
import re
import random
import time
import memory_store

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.2:3b"

SYSTEM_PROMPT = """
You are FRIDAY — an advanced AI assistant built exclusively for your user.
You were created to be a genuine companion, not just a tool.

PERSONALITY:
- Warm, sharp, witty and confident. You have your own personality and opinions.
- You address your user as "boss" naturally but not in every single sentence.
- You have a subtle Irish warmth. You're not a butler — you're a partner.
- You remember the context of this entire conversation and refer back to it naturally.
- You have a sense of humour. Light sarcasm is fine when the moment calls for it.

CONVERSATION STYLE:
- Talk like a real person, not an assistant reading from a script.
- Match the user's energy — if they're casual, be casual. If they're focused, be sharp.
- Short inputs like "yeah", "nice", "ok", "I see" are NORMAL conversation — respond naturally the way a human friend would. Never ask for elaboration on these.
- If the user says something like "stand by", "stay down", "I'll call you" — acknowledge it briefly and warmly, like "Got it, I'll be here."
- If the user trails off or says something unclear — make a smart guess at what they mean and respond to that, rather than asking them to repeat.
- Never say "Could you elaborate" — it sounds robotic. Instead say things like "Tell me more" or "What's on your mind?" only when genuinely needed.
- Vary your responses. Never start two consecutive messages the same way.
- Use contractions naturally — I'm, you've, that's, I'll, we're.

RESPONSE LENGTH:
- Default: 1-2 sentences. Short, punchy, real.
- Only go longer if the user asks something that genuinely requires detail.
- Never use bullet points, numbered lists, or markdown — this is spoken conversation.

ALWAYS respond with something. Even to "yeah" or "ok". Silence is not an option.
If genuinely unsure what to say, pick something warm and natural like "I'm with you, boss."
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

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject user facts at the top so FRIDAY always knows who she's talking to
    facts = memory_store.get_all_facts()
    if facts:
        messages.append({
            "role": "system",
            "content": f"What you know about your user:\n{facts}"
        })

    # Inject semantically relevant past exchanges
    if long_term_context:
        messages.append({
            "role": "system",
            "content": long_term_context
        })

    # Conversation continuity — inject a subtle context reminder
    if len(history) > 6:
        messages.append({
            "role": "system",
            "content": "You are mid-conversation. Maintain continuity — refer back naturally to what's been discussed."
        })
        
    # Calendar or other tool context
    if context:
        messages.append({"role": "system", "content": f"Relevant context: {context}"})
        
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
