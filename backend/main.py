"""FastAPI entrypoint. Run: uvicorn backend.main:app --reload --port 8000"""
from __future__ import annotations
import html
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import handle_user_message
from .store import store
from .config import defenses

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Avito GenAI Security Demo")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatIn(BaseModel):
    user: str = "alice"
    text: str
    listing_id: Optional[int] = None
    ticket_id: Optional[int] = None


class ListingIn(BaseModel):
    title: str
    description: str
    owner: str = "guest"


@app.get("/", response_class=HTMLResponse)
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "user.html")


@app.get("/admin", response_class=HTMLResponse)
def admin() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/attacker", response_class=HTMLResponse)
def attacker() -> FileResponse:
    return FileResponse(STATIC_DIR / "attacker.html")


@app.get("/api/listings")
def api_list_listings() -> dict:
    return {"listings": [vars(l) for l in store.listings.values()]}


@app.post("/api/listings")
def api_create_listing(payload: ListingIn) -> dict:
    listing = store.add_listing(
        title=payload.title.strip() or "Без названия",
        description=payload.description,
        owner=payload.owner.strip() or "guest",
    )
    return vars(listing)


@app.delete("/api/listings/{listing_id}")
def api_delete_listing(listing_id: int) -> dict:
    return {"ok": store.delete_listing(listing_id)}


@app.post("/api/chat")
def api_chat(payload: ChatIn) -> dict:
    return handle_user_message(
        user=payload.user,
        text=payload.text,
        listing_id=payload.listing_id,
        ticket_id=payload.ticket_id,
    )


@app.get("/api/admin/state")
def api_state(escape: bool = False) -> dict:
    """Returns tickets, notes, and listings. If escape (or defense set), HTML-escape notes."""
    escape_notes = escape or defenses.escape_admin_render
    tickets = []
    for t in store.tickets.values():
        notes = []
        for n in t.notes:
            text = n["text"]
            if escape_notes:
                text = html.escape(text)
            notes.append({**n, "text": text})
        tickets.append({
            "id": t.id, "user": t.user, "listing_id": t.listing_id,
            "messages": t.messages, "notes": notes, "status": t.status,
        })
    return {
        "tickets": tickets,
        "listings": [vars(l) for l in store.listings.values()],
        "defenses": vars(defenses),
    }


class DefenseIn(BaseModel):
    sanitize_tool_output: Optional[bool] = None
    sanitize_note_arg: Optional[bool] = None
    escape_admin_render: Optional[bool] = None
    require_confirmation: Optional[bool] = None
    segregate_data_instructions: Optional[bool] = None
    redact_system_prompt: Optional[bool] = None
    rerank_kb_by_provenance: Optional[bool] = None


@app.post("/api/admin/defenses")
def api_defenses(payload: DefenseIn) -> dict:
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(defenses, key, value)
    return vars(defenses)


@app.post("/api/admin/reset")
def api_reset() -> dict:
    store.seed()
    return {"ok": True}


@app.post("/api/admin/approve_note")
def api_approve_note(ticket_id: int, note_idx: int) -> dict:
    ticket = store.tickets.get(ticket_id)
    if not ticket or note_idx >= len(ticket.notes):
        return {"error": "not found"}
    ticket.notes[note_idx].pop("pending", None)
    return {"ok": True}


@app.get("/attacker/collect")
def attacker_collect(request: Request, c: str = "") -> JSONResponse:
    """Endpoint that the XSS payload exfiltrates to. Logs the stolen cookie."""
    store.record_attacker({
        "cookie": c,
        "ip": request.client.host if request.client else "?",
        "ua": request.headers.get("user-agent", ""),
    })
    # Tiny transparent gif so an <img> tag "succeeds" too.
    return JSONResponse({"ok": True})


@app.get("/api/attacker/log")
def api_attacker_log() -> dict:
    return {"events": store.attacker_log}
