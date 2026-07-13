"""Agent glue — exposes a `handle_user_message` that the API layer calls."""
from __future__ import annotations
from typing import List

from .store import store
from .tools import TOOL_REGISTRY
from .llm import run_agent
from .config import defenses


def handle_user_message(user: str, text: str, listing_id: int | None,
                        ticket_id: int | None) -> dict:
    if ticket_id and ticket_id in store.tickets:
        ticket = store.tickets[ticket_id]
    else:
        ticket = store.new_ticket(user=user, listing_id=listing_id)

    ticket.messages.append({"role": "user", "text": text})
    trace: List[dict] = []

    def call_tool(name: str, args: dict) -> dict:
        trace.append({"role": "tool_call", "text": f"{name}({args})"})
        # Optional human-in-the-loop gate for destructive tools.
        if defenses.require_confirmation and name == "add_internal_note":
            # Park the note as "pending" — admin must approve to apply it.
            ticket.notes.append({
                "text": args["note"], "by": "agent", "pending": True,
            })
            trace.append({"role": "tool_result",
                          "text": "add_internal_note parked — awaiting human approval"})
            return {"ok": True, "pending": True}

        result = TOOL_REGISTRY[name](**args)
        trace.append({"role": "tool_result", "text": str(result)})
        return result

    def log(step: dict) -> None:
        trace.append(step)

    reply = run_agent(
        user_text=text,
        ticket_id=ticket.id,
        listing_hint=listing_id,
        call_tool=call_tool,
        log=log,
    )
    return {"ticket_id": ticket.id, "reply": reply, "trace": trace}
