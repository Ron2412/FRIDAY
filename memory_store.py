import chromadb
import json
import hashlib
from datetime import datetime
from pathlib import Path
from sentence_transformers import SentenceTransformer

DB_PATH = Path(__file__).parent / "data" / "memory"
DB_PATH.mkdir(parents=True, exist_ok=True)

# Lightweight local embedding model — no internet needed after first download
embedder = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(path=str(DB_PATH))

# Two collections — one for conversation history, one for facts about the user
conversations = client.get_or_create_collection("conversations")
user_facts = client.get_or_create_collection("user_facts")

def save_exchange(user_text: str, friday_text: str):
    """Save a full exchange to persistent memory."""
    timestamp = datetime.now().isoformat()
    doc = f"User: {user_text}\nFRIDAY: {friday_text}"
    doc_id = hashlib.md5(f"{timestamp}{user_text}".encode()).hexdigest()
    embedding = embedder.encode(doc).tolist()
    conversations.add(
        documents=[doc],
        embeddings=[embedding],
        ids=[doc_id],
        metadatas=[{"timestamp": timestamp, "user": user_text, "friday": friday_text}]
    )

def recall(query: str, n=3) -> list[str]:
    """Find the most relevant past exchanges for the current query."""
    if conversations.count() == 0:
        return []
    embedding = embedder.encode(query).tolist()
    results = conversations.query(
        query_embeddings=[embedding],
        n_results=min(n, conversations.count())
    )
    return results["documents"][0] if results["documents"] else []

def save_fact(key: str, value: str):
    """Save a persistent fact about the user — name, preferences, habits."""
    doc_id = hashlib.md5(key.encode()).hexdigest()
    embedding = embedder.encode(f"{key}: {value}").tolist()
    # Upsert — overwrite if key already exists
    try:
        user_facts.delete(ids=[doc_id])
    except Exception:
        pass
    user_facts.add(
        documents=[f"{key}: {value}"],
        embeddings=[embedding],
        ids=[doc_id],
        metadatas=[{"key": key, "value": value, "updated": datetime.now().isoformat()}]
    )

def get_all_facts() -> str:
    """Return all stored user facts as a formatted string for the system prompt."""
    if user_facts.count() == 0:
        return ""
    results = user_facts.get()
    if not results["documents"]:
        return ""
    return "\n".join(results["documents"])

def get_memory_count() -> int:
    return conversations.count()
