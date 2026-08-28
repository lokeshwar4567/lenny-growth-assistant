from pathlib import Path
import re

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

def load_transcripts():
    documents = []
    for path in DATA_DIR.glob("*.txt"):
        text = path.read_text(encoding="utf-8")
        documents.append({
            "title": path.stem,
            "content": text
        })
    return documents

def retrieve(query: str, limit: int = 3):
    documents = load_transcripts()
    if not documents:
        return []

    terms = set(re.findall(r"\w+", query.lower()))
    results = []

    for doc in documents:
        words = set(re.findall(r"\w+", doc["content"].lower()))
        score = len(terms & words)
        if score:
            results.append((score, doc))

    results.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in results[:limit]]
