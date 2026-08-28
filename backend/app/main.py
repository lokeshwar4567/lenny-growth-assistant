from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import os
import requests
import uuid

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://lenny:lenny@localhost:5432/lenny"
)
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title="Lenny Growth Assistant")

class ChatRequest(BaseModel):
    message: str

@app.on_event("startup")
def startup():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id UUID PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY,
                session_id UUID REFERENCES chat_sessions(id),
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected",
        "provider": "ollama",
        "model": OLLAMA_MODEL
    }

@app.post("/api/sessions")
def create_session():
    session_id = uuid.uuid4()

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO chat_sessions (id) VALUES (:id)"),
            {"id": session_id}
        )

    return {"session_id": str(session_id)}

@app.get("/api/sessions")
def list_sessions():
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, created_at
                FROM chat_sessions
                ORDER BY created_at DESC
            """)
        ).mappings().all()

    return [dict(row) for row in rows]

def ask_ollama(messages):
    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        },
        timeout=120
    )
    response.raise_for_status()
    return response.json()["message"]["content"]

@app.post("/api/sessions/{session_id}/messages")
def send_message(session_id: str, request: ChatRequest):
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT id FROM chat_sessions WHERE id=:id"),
            {"id": session_uuid}
        ).first()

        if not exists:
            raise HTTPException(status_code=404, detail="Session not found")

        history = conn.execute(
            text("""
                SELECT role, content
                FROM messages
                WHERE session_id=:id
                ORDER BY created_at
            """),
            {"id": session_uuid}
        ).mappings().all()

    from backend.app.services.grounded_chat import grounded_chat

    history_list = [
        {"role": row["role"], "content": row["content"]}
        for row in history
    ]

    try:
        result = grounded_chat(request.message, history_list)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO messages
                (id, session_id, role, content)
                VALUES (:id, :session_id, 'user', :content)
            """),
            {
                "id": uuid.uuid4(),
                "session_id": session_uuid,
                "content": request.message
            }
        )

        conn.execute(
            text("""
                INSERT INTO messages
                (id, session_id, role, content)
                VALUES (:id, :session_id, 'assistant', :content)
            """),
            {
                "id": uuid.uuid4(),
                "session_id": session_uuid,
                "content": result["answer"]
            }
        )

    return {
        "session_id": session_id,
        "answer": result["answer"],
        "sources": result["sources"]
    }

@app.get("/")
def root():
    return {
        "name": "Lenny Growth Assistant",
        "status": "running"
    }

app.mount("/static", StaticFiles(directory="frontend", html=True), name="static")
