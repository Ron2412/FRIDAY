import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4


try:
    import chromadb
except ImportError:
    chromadb = None


@dataclass
class MemoryHit:
    text: str
    metadata: dict[str, Any]
    score: float


class MemoryStore:
    def __init__(self, persist_directory: str = "memory_db") -> None:
        self.persist_directory = persist_directory
        self._client = None
        self._short_term = None
        self._long_term = None
        self._fallback_short: list[dict[str, Any]] = []
        self._fallback_long: list[dict[str, Any]] = []

    def initialize(self) -> None:
        if chromadb is None:
            return

        self._client = chromadb.PersistentClient(path=self.persist_directory)
        self._short_term = self._client.get_or_create_collection("short_term_memory")
        self._long_term = self._client.get_or_create_collection("long_term_memory")

    async def initialize_async(self) -> None:
        await asyncio.to_thread(self.initialize)

    def _add_fallback(self, bucket: list[dict[str, Any]], text: str, metadata: dict[str, Any]) -> None:
        bucket.append({"id": str(uuid4()), "text": text, "metadata": metadata})

    def remember_short_term(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        metadata = metadata or {}
        metadata.setdefault("created_at", datetime.utcnow().isoformat())
        if self._short_term is not None:
            self._short_term.add(documents=[text], metadatas=[metadata], ids=[str(uuid4())])
            return
        self._add_fallback(self._fallback_short, text, metadata)

    async def remember_short_term_async(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        await asyncio.to_thread(self.remember_short_term, text, metadata)

    def remember_long_term(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        metadata = metadata or {}
        metadata.setdefault("created_at", datetime.utcnow().isoformat())
        if self._long_term is not None:
            self._long_term.add(documents=[text], metadatas=[metadata], ids=[str(uuid4())])
            return
        self._add_fallback(self._fallback_long, text, metadata)

    async def remember_long_term_async(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        await asyncio.to_thread(self.remember_long_term, text, metadata)

    def _search_fallback(
        self,
        bucket: list[dict[str, Any]],
        query: str,
        limit: int,
        hours: int | None = None,
    ) -> list[MemoryHit]:
        now = datetime.utcnow()
        terms = set(query.lower().split())
        hits: list[MemoryHit] = []

        for item in reversed(bucket):
            created_at = item["metadata"].get("created_at")
            if hours and created_at:
                try:
                    age = now - datetime.fromisoformat(created_at)
                    if age > timedelta(hours=hours):
                        continue
                except ValueError:
                    pass

            text = item["text"]
            overlap = sum(1 for token in text.lower().split() if token in terms)
            if overlap:
                hits.append(MemoryHit(text=text, metadata=item["metadata"], score=float(overlap)))
            if len(hits) >= limit:
                break

        return hits

    def recall(self, query: str, short_limit: int = 3, long_limit: int = 3) -> list[MemoryHit]:
        hits: list[MemoryHit] = []

        if self._short_term is not None:
            short = self._short_term.query(query_texts=[query], n_results=short_limit)
            for doc, meta, distance in zip(
                short.get("documents", [[]])[0],
                short.get("metadatas", [[]])[0],
                short.get("distances", [[]])[0] if short.get("distances") else [0.0] * short_limit,
            ):
                hits.append(MemoryHit(text=doc, metadata=meta or {}, score=float(distance)))
        else:
            hits.extend(self._search_fallback(self._fallback_short, query, short_limit, hours=6))

        if self._long_term is not None:
            long = self._long_term.query(query_texts=[query], n_results=long_limit)
            for doc, meta, distance in zip(
                long.get("documents", [[]])[0],
                long.get("metadatas", [[]])[0],
                long.get("distances", [[]])[0] if long.get("distances") else [0.0] * long_limit,
            ):
                hits.append(MemoryHit(text=doc, metadata=meta or {}, score=float(distance)))
        else:
            hits.extend(self._search_fallback(self._fallback_long, query, long_limit))

        return hits

    async def recall_async(self, query: str, short_limit: int = 3, long_limit: int = 3) -> list[MemoryHit]:
        return await asyncio.to_thread(self.recall, query, short_limit, long_limit)
