"""
Negotiation War Room — FastAPI backend.

Endpoints
─────────
GET  /                          → health check
POST /negotiate                 → start a new negotiation (non-blocking, returns session_id)
WS   /ws/{session_id}          → stream events for a session started via POST /negotiate
WS   /ws/live/{purchaser_type} → one-shot: start + stream a live LLM negotiation
WS   /ws/demo/{purchaser_type} → scripted demo (no LLM key required)
GET  /demo-data                 → scripted events as JSON (no WS required)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Negotiation War Room", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active negotiation sessions  {session_id: task}
_sessions: dict[str, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/")
async def health():
    return {"status": "ok", "service": "Negotiation War Room"}


# ---------------------------------------------------------------------------
# Start negotiation
# ---------------------------------------------------------------------------

class NegotiateRequest(BaseModel):
    purchaser_type: str = "tough"  # "tough" | "emergency"


@app.post("/negotiate")
async def start_negotiation(req: NegotiateRequest):
    session_id = str(uuid.uuid4())

    # Import here to avoid module-level side-effects at startup
    from agents import run_negotiation

    task = asyncio.create_task(run_negotiation(req.purchaser_type))
    _sessions[session_id] = task

    log.info("Negotiation %s started (purchaser_type=%s)", session_id, req.purchaser_type)
    return {"session_id": session_id, "purchaser_type": req.purchaser_type}


# ---------------------------------------------------------------------------
# WebSocket event stream
# ---------------------------------------------------------------------------

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    log.info("WS client connected for session %s", session_id)

    from agents import event_stream

    try:
        async for event in event_stream():
            await websocket.send_text(json.dumps(event))
            if event.get("type") == "negotiation_end":
                break
    except WebSocketDisconnect:
        log.info("WS client disconnected (session=%s)", session_id)
    except Exception as exc:
        log.error("WS error: %s", exc)
        await websocket.send_text(
            json.dumps({"type": "error", "message": str(exc)})
        )
    finally:
        if session_id in _sessions:
            _sessions.pop(session_id, None)


# ---------------------------------------------------------------------------
# Live WebSocket — starts a real LLM negotiation and streams its events
# ---------------------------------------------------------------------------

@app.websocket("/ws/live/{purchaser_type}")
async def websocket_live(websocket: WebSocket, purchaser_type: str = "tough"):
    """
    One-shot endpoint: connecting triggers a full live negotiation with
    Claude Haiku 4.5 tool-calling.  Events stream until negotiation_end.
    """
    await websocket.accept()
    log.info("Live WS connected (purchaser_type=%s)", purchaser_type)

    from agents import event_stream, run_negotiation

    # Start the negotiation concurrently with the streaming consumer
    negotiation_task = asyncio.create_task(run_negotiation(purchaser_type))

    try:
        async for event in event_stream():
            await websocket.send_text(json.dumps(event))
            if event.get("type") == "negotiation_end":
                break
    except WebSocketDisconnect:
        log.info("Live WS client disconnected early")
        negotiation_task.cancel()
    except Exception as exc:
        log.error("Live WS error: %s", exc)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
        negotiation_task.cancel()


# ---------------------------------------------------------------------------
# Demo data endpoint (no LLM key needed — scripted for the live demo)
# ---------------------------------------------------------------------------

DEMO_EVENTS = [
    {
        "type": "negotiation_start",
        "purchaser_type": "tough",
        "providers": {
            "provider_1": {"name": "Nova Kicks", "opening_ask": 180.0, "speed_days": 7, "warranty_months": 12},
            "provider_2": {"name": "SoleMaster", "opening_ask": 200.0, "speed_days": 3, "warranty_months": 24},
            "provider_3": {"name": "QuickShoe",  "opening_ask": 165.0, "speed_days": 2, "warranty_months": 6},
        },
    },
    # ── Round 1 ──────────────────────────────────────────────────────────────
    {"type": "thought", "actor": "PURCHASER", "tag": "STRATEGY",
     "content": "[Round 1] Analysing provider landscape. Active providers: ['provider_1', 'provider_2', 'provider_3']. My target price: $150.00."},
    {"type": "thought", "actor": "PURCHASER", "tag": "TOOL_CALL",
     "content": "price_oracle(quantity=10)"},
    {"type": "thought", "actor": "PURCHASER", "tag": "MATH_RESULT",
     "content": '{\n  "item": "Limited Edition Sneakers",\n  "quantity": 10,\n  "market_average_per_pair": 150.0,\n  "total_market_value": 1500.0,\n  "fair_range": {"low": 135.0, "high": 165.0},\n  "note": "Any offer more than 10 % above market average should be countered or rejected outright."\n}'},
    {"type": "thought", "actor": "PURCHASER", "tag": "DECISION",
     "content": "Market average is $150. My new target: $147.00. I will reject any offer above $154.35."},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "STRATEGY",
     "content": "QuickShoe considering concession. Current ask: $165.00. Purchaser target: $147.00."},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "TOOL_CALL",
     "content": "margin_validator(provider_id='provider_3', proposed_price=151.8)"},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "MATH_RESULT",
     "content": '{\n  "status": "APPROVED",\n  "provider_id": "provider_3",\n  "proposed_price": 151.8,\n  "floor_price": 105.0,\n  "margin_pct": 44.6,\n  "message": "Offer approved. Margin above floor: 44.6 %."\n}'},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "DECISION",
     "content": "Concession approved. New offer: $151.80 (margin 44.6 % above floor)."},
    {"type": "convergence", "data": {"round": 1, "gap": 4.8, "provider_id": "provider_3", "provider_name": "QuickShoe", "price": 151.8, "purchaser_target": 147.0}},
    {"type": "thought", "actor": "PURCHASER", "tag": "TOOL_CALL",
     "content": "utility_calculator(price=151.8, speed_days=2, warranty_months=6, purchaser_type='tough')"},
    {"type": "thought", "actor": "PURCHASER", "tag": "MATH_RESULT",
     "content": '{\n  "purchaser": "Purchaser A — Tough Buyer",\n  "overall_score": 50.12,\n  "dimension_scores": {"price": 48.5, "speed": 96.6, "warranty": 25.0},\n  "weights_used": {"price": "70%", "speed": "15%", "warranty": "15%"},\n  "verdict": "REJECT"\n}'},
    {"type": "radar", "data": {"price_score": 48.5, "speed_score": 96.6, "warranty_score": 25.0, "overall": 50.12, "provider": "QuickShoe"}},
    {"type": "thought", "actor": "PURCHASER", "tag": "DECISION",
     "content": "REJECT — QuickShoe offer at $151.80 scores 50.12/100 (need ≥ 55 AND price ≤ $154.35). Continuing pressure."},
    # ── Round 2 ──────────────────────────────────────────────────────────────
    {"type": "thought", "actor": "PURCHASER", "tag": "STRATEGY",
     "content": "[Round 2] QuickShoe still cheapest. Pushing harder. Target: $144.00."},
    {"type": "thought", "actor": "PURCHASER", "tag": "TOOL_CALL",
     "content": "price_oracle(quantity=10)"},
    {"type": "thought", "actor": "PURCHASER", "tag": "MATH_RESULT",
     "content": '{\n  "market_average_per_pair": 150.0,\n  "fair_range": {"low": 135.0, "high": 165.0}\n}'},
    {"type": "thought", "actor": "PURCHASER", "tag": "DECISION",
     "content": "Anchoring lower. New target: $144.00."},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "STRATEGY",
     "content": "QuickShoe considering concession. Current ask: $151.80. Purchaser target: $144.00."},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "TOOL_CALL",
     "content": "margin_validator(provider_id='provider_3', proposed_price=139.66)"},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "MATH_RESULT",
     "content": '{\n  "status": "APPROVED",\n  "provider_id": "provider_3",\n  "proposed_price": 139.66,\n  "floor_price": 105.0,\n  "margin_pct": 33.0\n}'},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "DECISION",
     "content": "Concession approved. New offer: $139.66 (margin 33.0 % above floor)."},
    {"type": "convergence", "data": {"round": 2, "gap": -4.34, "provider_id": "provider_3", "provider_name": "QuickShoe", "price": 139.66, "purchaser_target": 144.0}},
    {"type": "thought", "actor": "PURCHASER", "tag": "TOOL_CALL",
     "content": "utility_calculator(price=139.66, speed_days=2, warranty_months=6, purchaser_type='tough')"},
    {"type": "thought", "actor": "PURCHASER", "tag": "MATH_RESULT",
     "content": '{\n  "purchaser": "Purchaser A — Tough Buyer",\n  "overall_score": 57.3,\n  "dimension_scores": {"price": 61.2, "speed": 96.6, "warranty": 25.0},\n  "weights_used": {"price": "70%", "speed": "15%", "warranty": "15%"},\n  "verdict": "ACCEPT"\n}'},
    {"type": "radar", "data": {"price_score": 61.2, "speed_score": 96.6, "warranty_score": 25.0, "overall": 57.3, "provider": "QuickShoe"}},
    {"type": "thought", "actor": "PURCHASER", "tag": "DECISION",
     "content": "ACCEPT — QuickShoe offer at $139.66 scores 57.3/100. Deal closed!"},
    {
        "type": "negotiation_end",
        "outcome": "ACCEPT",
        "deal": {
            "provider_id": "provider_3",
            "provider_name": "QuickShoe",
            "price": 139.66,
            "speed_days": 2,
            "warranty_months": 6,
            "utility_score": 57.3,
        },
    },
]

# --- Demo with a VETO flash ---
DEMO_EVENTS_EMERGENCY = [
    {
        "type": "negotiation_start",
        "purchaser_type": "emergency",
        "providers": {
            "provider_1": {"name": "Nova Kicks", "opening_ask": 180.0, "speed_days": 7, "warranty_months": 12},
            "provider_2": {"name": "SoleMaster", "opening_ask": 200.0, "speed_days": 3, "warranty_months": 24},
            "provider_3": {"name": "QuickShoe",  "opening_ask": 165.0, "speed_days": 2, "warranty_months": 6},
        },
    },
    {"type": "thought", "actor": "PURCHASER", "tag": "STRATEGY",
     "content": "[Round 1] Emergency mode — speed is paramount (70% weight). Checking prices."},
    {"type": "thought", "actor": "PURCHASER", "tag": "TOOL_CALL", "content": "price_oracle(quantity=10)"},
    {"type": "thought", "actor": "PURCHASER", "tag": "MATH_RESULT",
     "content": '{"market_average_per_pair": 150.0, "fair_range": {"low": 135.0, "high": 165.0}}'},
    {"type": "thought", "actor": "PURCHASER", "tag": "DECISION",
     "content": "I need speed. QuickShoe (2 days) is the priority provider even at a price premium."},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "STRATEGY",
     "content": "QuickShoe smells urgency — minimal concession this round."},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "TOOL_CALL",
     "content": "margin_validator(provider_id='provider_3', proposed_price=155.0)"},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "MATH_RESULT",
     "content": '{"status": "APPROVED", "proposed_price": 155.0, "floor_price": 105.0, "margin_pct": 47.6}'},
    {"type": "thought", "actor": "PROVIDER_3", "tag": "DECISION", "content": "Offer $155.00 approved."},
    {"type": "convergence", "data": {"round": 1, "gap": 5.0, "provider_id": "provider_3", "provider_name": "QuickShoe", "price": 155.0, "purchaser_target": 150.0}},
    {"type": "thought", "actor": "PURCHASER", "tag": "TOOL_CALL",
     "content": "utility_calculator(price=155.0, speed_days=2, warranty_months=6, purchaser_type='emergency')"},
    {"type": "thought", "actor": "PURCHASER", "tag": "MATH_RESULT",
     "content": '{\n  "purchaser": "Purchaser B — Emergency Buyer",\n  "overall_score": 71.4,\n  "dimension_scores": {"price": 41.7, "speed": 96.6, "warranty": 25.0},\n  "weights_used": {"price": "20%", "speed": "70%", "warranty": "10%"},\n  "verdict": "ACCEPT"\n}'},
    {"type": "radar", "data": {"price_score": 41.7, "speed_score": 96.6, "warranty_score": 25.0, "overall": 71.4, "provider": "QuickShoe"}},
    # Veto flash — SoleMaster tries to go below floor to steal the deal
    {"type": "thought", "actor": "PROVIDER_2", "tag": "STRATEGY",
     "content": "SoleMaster sees deal closing with QuickShoe — desperate counteroffer at $100."},
    {"type": "thought", "actor": "PROVIDER_2", "tag": "TOOL_CALL",
     "content": "margin_validator(provider_id='provider_2', proposed_price=100.0)"},
    {"type": "thought", "actor": "PROVIDER_2", "tag": "MATH_RESULT",
     "content": '{\n  "status": "VETO",\n  "proposed_price": 100.0,\n  "floor_price": 125.0,\n  "shortfall": 25.0,\n  "message": "HARD VETO — proposed price $100.00 is $25.00 below the margin floor of $125.00. Offer BLOCKED."\n}'},
    {"type": "veto", "actor": "PROVIDER_2",
     "message": "HARD VETO — proposed price $100.00 is $25.00 below the margin floor of $125.00. Offer BLOCKED.",
     "proposed_price": 100.0, "floor_price": 125.0},
    {"type": "thought", "actor": "PROVIDER_2", "tag": "DECISION",
     "content": "VETO triggered — cannot send that offer. SoleMaster holds at $200.00."},
    {"type": "thought", "actor": "PURCHASER", "tag": "DECISION",
     "content": "QuickShoe scores 71.4/100 in emergency mode — ACCEPT. Closing with QuickShoe at $155.00."},
    {
        "type": "negotiation_end",
        "outcome": "ACCEPT",
        "deal": {
            "provider_id": "provider_3",
            "provider_name": "QuickShoe",
            "price": 155.0,
            "speed_days": 2,
            "warranty_months": 6,
            "utility_score": 71.4,
        },
    },
]


@app.get("/demo-data")
async def demo_data(purchaser_type: str = "tough"):
    events = DEMO_EVENTS if purchaser_type == "tough" else DEMO_EVENTS_EMERGENCY
    return {"events": events}


@app.websocket("/ws/demo/{purchaser_type}")
async def websocket_demo(websocket: WebSocket, purchaser_type: str = "tough"):
    """
    Streams the scripted demo events with realistic delays.
    No LLM key required — perfect for live demos.
    """
    await websocket.accept()
    events = DEMO_EVENTS if purchaser_type == "tough" else DEMO_EVENTS_EMERGENCY

    try:
        for event in events:
            await asyncio.sleep(0.6)
            await websocket.send_text(json.dumps(event))
            if event.get("type") == "negotiation_end":
                break
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
