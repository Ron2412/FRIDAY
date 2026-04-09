try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


def search_web(query: str) -> str:
    """Return concise web search results as system context for the LLM."""
    if DDGS is None:
        return (
            "System Context: Live web research is currently unavailable because "
            "the ddgs dependency is not installed."
        )

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
    except Exception as exc:
        return f"System Context: Live web research failed for this query. Error: {exc}"

    if not results:
        return "System Context: Live web research found no useful results for this query."

    lines = [
        "System Context: Fresh web research results. Use these as supporting factual context while keeping FRIDAY's natural, witty personality.",
    ]
    for item in results[:5]:
        title = (item.get("title") or "Untitled").strip()
        snippet = (item.get("body") or item.get("snippet") or "").strip()
        url = (item.get("href") or item.get("url") or "").strip()
        lines.append(f"- {title}: {snippet or 'No summary available.'} (Source: {url or 'Unknown'})")

    return "\n".join(lines)
