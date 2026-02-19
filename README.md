# ⚔️ Negotiation War Room

> **Demo:** Grounded Agents (Cyborgs) vs Solo LLMs — live negotiation for 10 pairs of Limited Edition Sneakers.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     React Frontend                       │
│                                                          │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ DealRadar│ │ Convergence  │ │    ThoughtFeed        │ │
│  │ (Recharts│ │ Line Chart   │ │  [STRATEGY]           │ │
│  │  Radar)  │ │ (gap closing)│ │  [TOOL_CALL]          │ │
│  └──────────┘ └──────────────┘ │  [MATH_RESULT]        │ │
│  VetoFlash (red overlay)       │  [DECISION]           │ │
│                                └──────────────────────┘ │
└───────────────────────┬─────────────────────────────────┘
                        │ WebSocket (JSON events)
┌───────────────────────┴─────────────────────────────────┐
│                   FastAPI Backend                        │
│                                                          │
│   LangGraph State Machine                                │
│   ┌───────────┐  ┌────────────┐  ┌──────────────────┐  │
│   │ Purchaser │→ │  Provider  │→ │    Evaluator     │  │
│   │   Node    │  │   Node     │  │     Node         │  │
│   └───────────┘  └────────────┘  └──────────────────┘  │
│                                                          │
│   Grounding Engine (logic_engine.py)                     │
│   ┌──────────────────┐  ┌──────────────────────────┐    │
│   │ UtilityCalculator│  │    MarginValidator        │    │
│   │ (0-100 score)    │  │    (HARD VETO guard)      │    │
│   └──────────────────┘  └──────────────────────────┘    │
│   ┌──────────────────┐                                   │
│   │   PriceOracle    │  market_avg=$150                  │
│   │ (anti-hallucin.) │                                   │
│   └──────────────────┘                                   │
└─────────────────────────────────────────────────────────┘
```

## The Three Grounding Tools

| Tool | Purpose | Who Uses It |
|------|---------|-------------|
| `PriceOracle` | Returns market average ($150) to prevent anchoring bias | Purchaser Agent |
| `UtilityCalculator` | Scores deals 0–100 using hidden buyer weights; returns REJECT if below 55 | Purchaser Agent |
| `MarginValidator` | HARD VETOs any provider offer below their floor price | Provider Agents |

### Purchaser Weight Profiles

| Profile | Price | Speed | Warranty |
|---------|-------|-------|----------|
| Tough Buyer | **70%** | 15% | 15% |
| Emergency Buyer | 20% | **70%** | 10% |

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # add OPENAI_API_KEY if running live agents
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev               # http://localhost:3000
```

### Docker

```bash
docker-compose up --build
```

## WebSocket Events

| Event | Payload | Description |
|-------|---------|-------------|
| `negotiation_start` | providers, purchaser_type | Session begins |
| `thought` | actor, tag, content | Agent inner monologue |
| `radar` | price/speed/warranty scores | Deal shape updated |
| `convergence` | round, gap, price | Price gap data point |
| `veto` | message, proposed_price, floor_price | MarginValidator blocked an offer |
| `negotiation_end` | outcome, deal | Session complete |

## Key Demo Moment

The Purchaser Agent **REJECTS** QuickShoe's Round 1 offer of **$151.80** even though it is below the market average — because `UtilityCalculator` returns a score of **50.12/100** (Tough Buyer weights: 70% price sensitivity means a barely-below-market price is still insufficient). Only after Round 2's concession to **$139.66** does the score reach **57.3/100**, triggering `ACCEPT`.

This is the core proof point: a solo LLM would have said _"Great deal!"_ at $151.80. The Grounded Agent says _"Math says no."_
