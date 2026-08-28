from backend.app.services.retrieval import retrieve
from backend.app.main import ask_ollama

def grounded_chat(question, history=None):
    docs = retrieve(question)

    if not docs:
        return {
            "answer": "I don't have enough evidence in the available transcript knowledge base to answer that confidently.",
            "sources": []
        }

    context = "\n\n".join(
        f"Source: {doc['title']}\n{doc['content']}"
        for doc in docs
    )

    messages = [{
        "role": "system",
        "content": """You are Lenny Growth Assistant.
Answer ONLY using the supplied transcript context.
If the context does not support the answer, say that the evidence is insufficient.
Do not invent transcript facts."""
    }]

    if history:
        messages.extend(history)

    messages.append({
        "role": "user",
        "content": f"""Transcript context:

{context}

Question:
{question}

Give a concise, useful answer grounded in the transcript."""
    })

    answer = ask_ollama(messages)

    return {
        "answer": answer,
        "sources": [{"title": d["title"]} for d in docs]
    }
