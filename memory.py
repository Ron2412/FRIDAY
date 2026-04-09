class Memory:
    def __init__(self, capacity=30):
        self.capacity = capacity
        # list of dictionaries: {"role": "user" | "assistant", "content": "..."}
        self.history = []

    def add_interaction(self, role, content):
        self.history.append({"role": role, "content": content})
        # Keep only the last N turns
        if len(self.history) > self.capacity:
            # We want to remove the oldest items.
            # If we slice the last capacity elements, it trims the oldest.
            self.history = self.history[-self.capacity:]

    def get_history(self):
        return self.history

    def clear(self):
        self.history = []


import memory_store

def persist_exchange(user_text: str, friday_text: str):
    """Call this after every exchange to save to ChromaDB."""
    memory_store.save_exchange(user_text, friday_text)

def get_relevant_context(query: str) -> str:
    """Retrieve semantically relevant past exchanges for current query."""
    recalled = memory_store.recall(query, n=3)
    if not recalled:
        return ""
    return "Relevant past context:\n" + "\n---\n".join(recalled)
