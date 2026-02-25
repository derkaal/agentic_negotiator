"""
Negotiation War Room — FastAPI backend.

Endpoints
─────────
GET  /                          → health check
WS   /ws/market/{scenario}      → N-to-N MBMPMS market simulation (3×3 buyers × sellers)
WS   /ws/stress-test/{scenario_id} → Stress test scenario execution
GET  /market-config              → Market buyer/seller configurations
"""

from __future__ import annotations

import asyncio
import json
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Negotiation War Room", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/")
async def health():
    return {"status": "ok", "service": "Negotiation War Room - Stress Test Suite"}


# ---------------------------------------------------------------------------
# N-to-N Market (MBMPMS) endpoint
# ---------------------------------------------------------------------------

try:
    from market_tasks import run_market_3x3, BUYER_CONFIGS, SELLER_CONFIGS
    _MARKET_AVAILABLE = True
except Exception as _mkt_err:  # noqa: BLE001
    log.warning("Market tasks unavailable: %s", _mkt_err)
    _MARKET_AVAILABLE = False


@app.websocket("/ws/market/{scenario}")
async def websocket_market(websocket: WebSocket, scenario: str = "used_car"):
    """
    Run an N-to-N MBMPMS market simulation and stream events.

    scenario: 'used_car'  (3 Buyers × 3 Sellers, Honda Civic 2021)

    Event types:
      market_start, market_round, pair_update, market_switch,
      deal_closed, deal_rate, market_score, market_end
    """
    await websocket.accept()
    log.info("Market WS connected (scenario=%s)", scenario)

    if not _MARKET_AVAILABLE:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Market tasks not available (import error).",
        }))
        await websocket.close()
        return

    supported = {"used_car", "sneaker"}
    if scenario not in supported:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Unknown scenario '{scenario}'. Supported: {sorted(supported)}",
        }))
        await websocket.close()
        return

    try:
        async for event in run_market_3x3(scenario=scenario, max_rounds=15):
            await websocket.send_text(json.dumps(event))
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        log.info("Market WS disconnected (scenario=%s)", scenario)
    except Exception as exc:  # noqa: BLE001
        log.exception("Market WS error: %s", exc)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass


@app.get("/market-config")
async def market_config():
    """Return buyer/seller configurations for the market scenario."""
    if not _MARKET_AVAILABLE:
        return {"available": False}
    return {
        "available": True,
        "buyers": list(BUYER_CONFIGS.values()),
        "sellers": list(SELLER_CONFIGS.values()),
    }


# ---------------------------------------------------------------------------
# Stress Test Scenarios
# ---------------------------------------------------------------------------

@app.websocket("/ws/stress-test/{scenario_id}")
async def stress_test_websocket(websocket: WebSocket, scenario_id: str):
    """
    WebSocket endpoint for running stress test scenarios.
    
    Args:
        scenario_id: Scenario identifier
            - "adversarial_buyer": Scenario 1
            - "information_asymmetry": Scenario 2
    """
    await websocket.accept()
    log.info("Stress test WS connected (scenario=%s)", scenario_id)
    
    try:
        from stress_scenarios.runner import get_runner
        from stress_scenarios.config_loader import load_config
        from stress_scenarios.scenarios.adversarial_buyer import (
            AdversarialBuyerScenario
        )
        from stress_scenarios.scenarios.information_asymmetry import (
            InformationAsymmetryScenario
        )
        
        # Register scenarios
        runner = get_runner()
        runner.register_scenario("adversarial_buyer", AdversarialBuyerScenario)
        runner.register_scenario(
            "information_asymmetry",
            InformationAsymmetryScenario
        )
        
        # Load config
        try:
            config = load_config(scenario_id)
        except FileNotFoundError:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Scenario '{scenario_id}' not found"
            }))
            await websocket.close()
            return
        
        # Stream scenario execution
        async for event in runner.run_scenario_stream(scenario_id, config):
            await websocket.send_text(json.dumps(event))
            await asyncio.sleep(0)
            
            if event.get("type") == "scenario_complete":
                break
            elif event.get("type") == "scenario_error":
                break
        
    except WebSocketDisconnect:
        log.info("Stress test WS disconnected (scenario=%s)", scenario_id)
    except Exception as exc:
        log.exception("Stress test WS error: %s", exc)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(exc)
            }))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
