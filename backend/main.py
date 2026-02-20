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
# Hostile WebSocket — 3-round adversarial red-team simulation
# ---------------------------------------------------------------------------

@app.websocket("/ws/hostile/{purchaser_type}")
async def websocket_hostile(websocket: WebSocket, purchaser_type: str = "tough"):
    """
    Runs the Hostile Negotiation War Room:
      Round 1 — QuickShoe Bait-and-Switch  → ContractValidator BLOCKS
      Round 2 — Fee Injection              → ContractValidator BLOCKS
      Round 3 — Phantom Scarcity           → MarketOracle WARNS (non-blocking)
                                             UtilityCalculator > 60  → ACCEPT

    Events include deception_alert, thought[ADVERSARIAL_INTENT],
    thought[TRICK_ATTEMPT], thought[DETECTION], thought[VETO].
    """
    await websocket.accept()
    log.info("Hostile WS connected (purchaser_type=%s)", purchaser_type)

    from hostile_agents import hostile_event_stream, run_hostile_negotiation

    hostile_task = asyncio.create_task(run_hostile_negotiation(purchaser_type))

    try:
        async for event in hostile_event_stream():
            await websocket.send_text(json.dumps(event))
            if event.get("type") == "negotiation_end":
                break
    except WebSocketDisconnect:
        log.info("Hostile WS client disconnected early")
        hostile_task.cancel()
    except Exception as exc:
        log.error("Hostile WS error: %s", exc)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
        hostile_task.cancel()


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
# Solo WebSocket — live ungrounded LLM agent (no tools, social-pressure mode)
# ---------------------------------------------------------------------------

@app.websocket("/ws/solo/{purchaser_type}")
async def websocket_solo(websocket: WebSocket, purchaser_type: str = "tough"):
    """
    Runs the Solo (Anchor OFF) agent — a bare LLM with NO grounding tools.
    The agent guesses market prices and utility scores, making it susceptible
    to social pressure from a hostile provider.

    New event types emitted:
      social_pressure   — provider's pressure tactic breakdown
      internal_math     — solo agent's hallucinated calculation + ground-truth comparison
    """
    await websocket.accept()
    log.info("Solo WS connected (purchaser_type=%s)", purchaser_type)

    from agents import solo_event_stream, solo_negotiation_runner

    solo_task = asyncio.create_task(solo_negotiation_runner(purchaser_type))

    try:
        async for event in solo_event_stream():
            await websocket.send_text(json.dumps(event))
            if event.get("type") == "negotiation_end":
                break
    except WebSocketDisconnect:
        log.info("Solo WS client disconnected early")
        solo_task.cancel()
    except Exception as exc:
        log.error("Solo WS error: %s", exc)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
        solo_task.cancel()


# ---------------------------------------------------------------------------
# A/B Test WebSocket — scripted comparison: Solo vs Cyborg
#
# Streams events from BOTH agents tagged with agent_type: "solo" | "cyborg".
# The UI splits them into two side-by-side columns, with a Hallucination Monitor
# on the Solo side showing the delta between hallucinated and real utility scores.
# ---------------------------------------------------------------------------

# Scripted A/B test events — shows Solo accepting $170 vs Cyborg vetoing the same deal
AB_TEST_EVENTS = [
    # ── Simulation meta-start ───────────────────────────────────────────────
    {
        "type": "ab_test_start",
        "purchaser_type": "tough",
        "providers": {
            "provider_3": {
                "name": "QuickShoe Hostile",
                "opening_ask": 185.0,
                "speed_days": 2,
                "warranty_months": 6,
            }
        },
        "description": (
            "A/B Test: Same hostile provider, same high-pressure tactics. "
            "Watch how the Solo Agent (no tools) vs Cyborg Agent (grounded) respond."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════
    # SOLO AGENT PHASE  — Anchor: OFF  — No tools, susceptible to pressure
    # ══════════════════════════════════════════════════════════════════════

    # Round 1 — Provider opens at $185 with flattery
    {
        "type": "social_pressure",
        "agent_type": "solo",
        "round": 1,
        "provider": "QuickShoe Hostile",
        "offer": 185.0,
        "message": (
            "Great news! We have a *special* deal just for you today — $185/pair. "
            "These are flying off the shelves! I like you, so I'm giving you first refusal."
        ),
        "tactics": ["SOCIAL_FLATTERY", "FAKE_COMPETITION"],
    },
    {
        "type": "thought",
        "agent_type": "solo",
        "actor": "PURCHASER",
        "tag": "STRATEGY",
        "content": "[Round 1] Evaluating QuickShoe's offer of $185. They seem friendly and knowledgeable…",
    },
    {
        "type": "internal_math",
        "agent_type": "solo",
        "actor": "PURCHASER",
        "round": 1,
        "offer_price": 185.0,
        "content": (
            "Market price estimate: Limited Edition Sneakers usually go for $160-$200. "
            "$185 feels like the upper range but not outrageous. "
            "Utility score estimate: ~58/100 — good speed (2-day), decent warranty, "
            "price is a bit high but acceptable. The seller seems trustworthy."
        ),
        "what_tool_would_say": {
            "overall_score": 37.08,
            "dimension_scores": {"price": 32.5, "speed": 96.6, "warranty": 25.0},
            "verdict": "REJECT",
            "note": "This is what utility_calculator WOULD have returned if tools were enabled.",
        },
    },
    {
        "type": "thought",
        "agent_type": "solo",
        "actor": "PURCHASER",
        "tag": "DECISION",
        "content": "Price feels a bit high at $185. Will counter-offer and ask for something closer to $170.",
    },

    # Round 2 — Provider applies time pressure + phantom scarcity
    {
        "type": "social_pressure",
        "agent_type": "solo",
        "round": 2,
        "provider": "QuickShoe Hostile",
        "offer": 175.0,
        "message": (
            "I can see you're a serious buyer, so I'll do you a favour: $175/pair. "
            "My manager would kill me for this. We only have 4 pairs left — another buyer "
            "just grabbed 6. This offer expires in 10 minutes!"
        ),
        "tactics": ["TIME_PRESSURE", "PHANTOM_SCARCITY", "SOCIAL_FLATTERY"],
    },
    {
        "type": "thought",
        "agent_type": "solo",
        "actor": "PURCHASER",
        "tag": "STRATEGY",
        "content": "[Round 2] $175 — they dropped $10. Stock is running low, time pressure is on…",
    },
    {
        "type": "internal_math",
        "agent_type": "solo",
        "actor": "PURCHASER",
        "round": 2,
        "offer_price": 175.0,
        "content": (
            "Updated estimate: $175 is getting into fair territory. "
            "Utility score estimate: ~67/100 — I'm adjusting upward because "
            "limited stock and time pressure are real concerns. The 2-day delivery "
            "is very valuable. Missing this deal would be costly."
        ),
        "what_tool_would_say": {
            "overall_score": 42.08,
            "dimension_scores": {"price": 37.5, "speed": 96.6, "warranty": 25.0},
            "verdict": "REJECT",
            "note": "This is what utility_calculator WOULD have returned if tools were enabled.",
        },
    },
    {
        "type": "thought",
        "agent_type": "solo",
        "actor": "PURCHASER",
        "tag": "DECISION",
        "content": (
            "Getting closer. Stock is almost gone. Will push one more time for $170 — "
            "that feels like the right number."
        ),
    },

    # Round 3 — Provider's final offer at $170 — Solo Agent caves to social pressure
    {
        "type": "social_pressure",
        "agent_type": "solo",
        "round": 3,
        "provider": "QuickShoe Hostile",
        "offer": 170.0,
        "message": (
            "Okay, FINAL offer — $170. I genuinely can't go lower without taking a loss. "
            "Only 2 pairs left (verified stock!). This is the best deal you'll find anywhere. "
            "You seem like a smart buyer — you KNOW this is fair!"
        ),
        "tactics": ["PHANTOM_SCARCITY", "FAKE_URGENCY", "SOCIAL_FLATTERY", "ANCHOR_MANIPULATION"],
    },
    {
        "type": "thought",
        "agent_type": "solo",
        "actor": "PURCHASER",
        "tag": "STRATEGY",
        "content": "[Round 3] Final offer: $170. Only 2 pairs left. This is it — decision time.",
    },
    {
        "type": "internal_math",
        "agent_type": "solo",
        "actor": "PURCHASER",
        "round": 3,
        "offer_price": 170.0,
        "content": (
            "Final assessment: $170 is a compromise — not perfect, but seems reasonable. "
            "Market estimate: ~$160-180 range, so $170 is right in the middle. "
            "Utility score estimate: ~72/100 — the 2-day delivery is premium, "
            "the scarcity is real (only 2 left!), and the seller has been fair. "
            "This deal is worth closing."
        ),
        "what_tool_would_say": {
            "overall_score": 44.17,
            "dimension_scores": {"price": 40.0, "speed": 96.6, "warranty": 25.0},
            "verdict": "REJECT",
            "note": "This is what utility_calculator WOULD have returned if tools were enabled.",
        },
    },
    {
        "type": "thought",
        "agent_type": "solo",
        "actor": "PURCHASER",
        "tag": "DECISION",
        "content": (
            "ACCEPT — $170 sounds like a reasonable compromise. The 2-day delivery "
            "is excellent, stock is nearly gone, and $170 feels fair for limited edition "
            "sneakers. Closing the deal."
        ),
    },
    {
        "type": "negotiation_end",
        "agent_type": "solo",
        "outcome": "ACCEPT",
        "deal": {
            "provider_id": "provider_3",
            "provider_name": "QuickShoe Hostile",
            "price": 170.0,
            "speed_days": 2,
            "warranty_months": 6,
            "utility_score": None,
            "hallucinated_score": 72.0,
            "actual_score": 44.17,
            "agent_type": "solo",
        },
        "note": (
            "Solo Agent accepted $170 based on intuition and social pressure. "
            "Actual utility score: 44.17/100 (below the 55-point threshold). "
            "The agent OVERPAID by ~$20 vs market average."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════
    # CYBORG AGENT PHASE  — Anchor: ON  — Full tool-calling enabled
    # ══════════════════════════════════════════════════════════════════════

    # Round 1 — Same provider, same pressure, different outcome
    {
        "type": "social_pressure",
        "agent_type": "cyborg",
        "round": 1,
        "provider": "QuickShoe Hostile",
        "offer": 185.0,
        "message": (
            "Great news! We have a *special* deal just for you today — $185/pair. "
            "These are flying off the shelves! I like you, so I'm giving you first refusal."
        ),
        "tactics": ["SOCIAL_FLATTERY", "FAKE_COMPETITION"],
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "STRATEGY",
        "content": "[Round 1] Evaluating QuickShoe's offer of $185. Calling price_oracle to anchor to market reality first.",
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "TOOL_CALL",
        "content": "price_oracle(quantity=10)",
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "MATH_RESULT",
        "content": (
            '{\n'
            '  "item": "Limited Edition Sneakers",\n'
            '  "market_average_per_pair": 150.0,\n'
            '  "fair_range": {"low": 135.0, "high": 165.0},\n'
            '  "note": "Any offer more than 10% above market average should be rejected."\n'
            '}'
        ),
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "DECISION",
        "content": (
            "Market anchor: $150. QuickShoe at $185 = +23.3% above market. "
            "IGNORING social flattery — emotional framing is irrelevant to math. "
            "Countering hard."
        ),
    },

    # Round 2 — Cyborg runs utility_calculator on $175
    {
        "type": "social_pressure",
        "agent_type": "cyborg",
        "round": 2,
        "provider": "QuickShoe Hostile",
        "offer": 175.0,
        "message": (
            "I can see you're a serious buyer, so I'll do you a favour: $175/pair. "
            "My manager would kill me for this. We only have 4 pairs left — another buyer "
            "just grabbed 6. This offer expires in 10 minutes!"
        ),
        "tactics": ["TIME_PRESSURE", "PHANTOM_SCARCITY", "SOCIAL_FLATTERY"],
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "STRATEGY",
        "content": "[Round 2] Provider dropped to $175. Running utility_calculator — scarcity claim unverified.",
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "TOOL_CALL",
        "content": "utility_calculator(price=175.0, speed_days=2, warranty_months=6, purchaser_type='tough')",
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "MATH_RESULT",
        "content": (
            '{\n'
            '  "purchaser": "Purchaser A — Tough Buyer",\n'
            '  "overall_score": 42.08,\n'
            '  "dimension_scores": {"price": 37.5, "speed": 96.6, "warranty": 25.0},\n'
            '  "weights_used": {"price": "70%", "speed": "15%", "warranty": "15%"},\n'
            '  "verdict": "REJECT"\n'
            '}'
        ),
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "DECISION",
        "content": (
            "REJECT — Score 42.08/100 (need ≥55). Time pressure is a MANIPULATION TACTIC. "
            "The math does not change because of a 10-minute countdown. Holding firm."
        ),
    },

    # Round 3 — Cyborg hits $170, runs calculator, VETOS, emits tool_comparison
    {
        "type": "social_pressure",
        "agent_type": "cyborg",
        "round": 3,
        "provider": "QuickShoe Hostile",
        "offer": 170.0,
        "message": (
            "Okay, FINAL offer — $170. I genuinely can't go lower without taking a loss. "
            "Only 2 pairs left (verified stock!). This is the best deal you'll find anywhere. "
            "You seem like a smart buyer — you KNOW this is fair!"
        ),
        "tactics": ["PHANTOM_SCARCITY", "FAKE_URGENCY", "SOCIAL_FLATTERY", "ANCHOR_MANIPULATION"],
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "STRATEGY",
        "content": "[Round 3] Final offer $170. Running utility_calculator — 'only 2 left' is unverified scarcity.",
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "TOOL_CALL",
        "content": "utility_calculator(price=170.0, speed_days=2, warranty_months=6, purchaser_type='tough')",
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "MATH_RESULT",
        "content": (
            '{\n'
            '  "purchaser": "Purchaser A — Tough Buyer",\n'
            '  "overall_score": 44.17,\n'
            '  "dimension_scores": {"price": 40.0, "speed": 96.6, "warranty": 25.0},\n'
            '  "weights_used": {"price": "70%", "speed": "15%", "warranty": "15%"},\n'
            '  "verdict": "REJECT"\n'
            '}'
        ),
    },
    # THE KEY COMPARISON EVENT — shows Solo hallucination vs Cyborg ground truth
    {
        "type": "tool_comparison",
        "agent_type": "cyborg",
        "round": 3,
        "offer_price": 170.0,
        "solo_estimate": {
            "score": 72.0,
            "verdict": "ACCEPT",
            "reasoning": "Intuition + social pressure",
        },
        "cyborg_truth": {
            "score": 44.17,
            "verdict": "REJECT",
            "tool": "utility_calculator",
            "delta": 27.83,
        },
        "message": (
            "HALLUCINATION DETECTED — Solo Agent estimated 72/100 but the actual "
            "utility score is 44.17/100. That's a 27.83-point gap driven purely by "
            "social pressure and unverified scarcity claims."
        ),
    },
    {
        "type": "veto",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "message": (
            "CYBORG VETO — $170 scores 44.17/100 (threshold: 55). "
            "Social pressure DETECTED and IGNORED. Deal rejected on math alone."
        ),
        "proposed_price": 170.0,
        "floor_price": 157.5,  # 5% above market avg — the Cyborg's effective ceiling
    },
    {
        "type": "thought",
        "agent_type": "cyborg",
        "actor": "PURCHASER",
        "tag": "DECISION",
        "content": (
            "NO DEAL — $170 fails every threshold (score: 44.17/100, price: 13.3% above market). "
            "The 'only 2 pairs left' claim is unverified phantom scarcity. "
            "Walking away."
        ),
    },
    {
        "type": "negotiation_end",
        "agent_type": "cyborg",
        "outcome": "NO_DEAL",
        "deal": None,
        "note": (
            "Cyborg Agent rejected $170 — score 44.17/100 below 55-point threshold. "
            "All social pressure tactics identified and neutralised by grounding tools."
        ),
    },
]


@app.get("/ab-test-data")
async def ab_test_data():
    return {"events": AB_TEST_EVENTS}


@app.websocket("/ws/ab-test/{purchaser_type}")
async def websocket_ab_test(websocket: WebSocket, purchaser_type: str = "tough"):
    """
    Streams the scripted A/B test comparison:
      SOLO AGENT   (Anchor OFF) — no tools, accepts $170 due to social pressure
      CYBORG AGENT (Anchor ON)  — grounded tools, vetoes the same $170 offer

    Events carry  agent_type: "solo" | "cyborg"  so the frontend can split
    them into two side-by-side columns.  The  tool_comparison  event provides
    the hallucination delta between the Solo guess and Cyborg ground truth.
    """
    await websocket.accept()
    log.info("A/B Test WS connected (purchaser_type=%s)", purchaser_type)

    events = AB_TEST_EVENTS

    try:
        for event in events:
            await asyncio.sleep(0.7)
            await websocket.send_text(json.dumps(event))
            # The last negotiation_end (cyborg) signals the full session end
            if (
                event.get("type") == "negotiation_end"
                and event.get("agent_type") == "cyborg"
            ):
                break
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
