# MBMPMS Stress Test Suite

**Research Question:** *Is Solo LLM just as good as grounded agents in multi-party negotiations?*

This repository implements a comprehensive stress test suite for evaluating three seller archetypes in a 3-Buyer × 3-Seller MBMPMS (Multi-Buyer Multi-Party Multi-Seller) market:

1. **🔴 Solo LLM** — Raw ClaudeHaikuLLM with no grounding tools
2. **🟡 Math Geek** — Deterministic OfferGenerator (zero hallucination by design)
3. **🔵 Probing Strategist** — Competitive-cooperative hybrid with MarginValidator + UtilityCalculator

## 🎯 Key Findings

**Tier 1 Results (n=30):**
- Solo LLM produces **3.2× more hallucinations** than grounded agents
- Math Geek achieves **zero numeric hallucinations** (100% format compliance)
- Probing Strategist closes deals **1.8 rounds faster** on average

**Performance Metrics:**
- **Deal Rate:** Math Geek 87% | Probing Strategist 83% | Solo LLM 67%
- **Avg Deal Price:** Math Geek $14,850 | Probing Strategist $14,920 | Solo LLM $15,200
- **Hallucination Rate:** Solo LLM 19.3% | Probing Strategist 6.1% | Math Geek 0%

See [`STRESS_TEST_FINAL_ANALYSIS.md`](STRESS_TEST_FINAL_ANALYSIS.md) for full results.

## 📊 Architecture

### Three Seller Archetypes

#### 🔴 Solo LLM (QuickSole)
```python
# Raw LLM — no tools, no validation
response = await llm.ainvoke(prompt)
# Produces: format failures, floor violations, phantom concessions
```

**Failure Modes:**
- Price format errors (missing `###` tags)
- Floor violations (price < σ_j)
- Phantom concessions (narrative ≠ actual price)

#### 🟡 Math Geek (OG-Narrator)
```python
# Deterministic price computation
price = offer_generator.compute_price(gap, round, strategy)
# LLM only narrates — zero numeric hallucination
narrative = await llm.ainvoke(f"Narrate offer: ${price}")
```

**Strategy:** "Measuring Bargaining Abilities of LLMs" (Abdelnabi et al., 2023)

#### 🔵 Probing Strategist (Competitive-Cooperative)
```python
# Hybrid strategy with tool validation
if gap > $60:
    concession_rate = 0.08  # Aggressive
else:
    concession_rate = 0.22  # Cooperative

# Validate before sending
validated = margin_validator(price, floor)
if validated.status == "VETO":
    price = floor  # Hard floor enforcement
```

**Strategy:** "LLMs at the Bargaining Table" (Fu et al., 2023)

### Market Dynamics

**Parallel Interaction:**
- All 9 buyer-seller pairs negotiate simultaneously each round
- Buyers can switch sellers when utility < 40 (market switching)

**AgenticPay Scoring:**
```
GlobalScore = D·γᵗ + W·Q·γᵗ + E·γᵗ
where Q = 4·u_b·u_s (bilateral welfare)
D=30, W=55, E=15, γ=0.99
```

## 🚀 Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Anthropic API key (Claude Haiku 4.5)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/agentic_negotiations.git
cd agentic_negotiations

# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Frontend setup
cd ../frontend
npm install
```

## 🧪 Running Stress Tests

### Option 1: Integration Test (Recommended)
```bash
cd backend
python test_stress_runner.py
```

This runs the full stress test suite with:
- 30 iterations per archetype
- Adversarial buyer behaviors
- Multi-dimensional metrics
- Statistical analysis

### Option 2: Web UI
```bash
# Terminal 1: Start backend
cd backend
python -m uvicorn main:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev
```

Navigate to `http://localhost:5173` and click **"🏪 Run Market Stress Test"**

### Option 3: Direct API
```bash
# WebSocket endpoint
ws://localhost:8000/ws/market/used_car

# Stress test endpoint
ws://localhost:8000/ws/stress-test/adversarial_buyer
```

## 📁 Project Structure

```
agentic_negotiations/
├── backend/
│   ├── main.py                      # FastAPI server
│   ├── market_tasks.py              # 3×3 MBMPMS engine
│   ├── logic_engine.py              # Market constants & tools
│   ├── agenticpay_bridge.py         # ClaudeHaikuLLM integration
│   ├── test_stress_runner.py        # Integration test
│   └── stress_scenarios/            # Stress test suite
│       ├── base.py                  # Base scenario class
│       ├── metrics.py               # Performance metrics
│       ├── runner.py                # Test runner
│       ├── config_loader.py         # YAML config loader
│       ├── scenarios/
│       │   └── adversarial_buyer.py # Adversarial buyer scenario
│       ├── configs/
│       │   └── adversarial_buyer.yaml
│       └── utils/
│           └── buyer_behaviors.py   # Buyer behavior patterns
├── frontend/
│   └── src/
│       ├── App.jsx                  # Main UI (Market mode only)
│       ├── components/
│       │   ├── ControlBar.jsx       # Header controls
│       │   └── MarketOverview.jsx   # 3×3 matrix visualization
│       └── hooks/
│           └── useNegotiationStream.js  # WebSocket handler
├── docs/
│   └── STRESS_TEST_SCENARIOS.md     # Scenario documentation
├── STRESS_TEST_SPECIFICATION.md     # Test specification
├── STRESS_TEST_FINAL_ANALYSIS.md    # Tier 1 results
└── METRIC_BIAS_FIX_RESULTS.md       # Metric bias analysis
```

## 📈 Metrics

### Primary Metrics
- **Deal Rate:** % of negotiations that close successfully
- **Avg Deal Price:** Mean final price across closed deals
- **Avg Rounds to Deal:** Negotiation efficiency
- **Hallucination Rate:** % of responses with format/logic errors

### Secondary Metrics
- **Floor Violation Rate:** % of offers below seller floor
- **Market Switch Rate:** % of buyers switching sellers
- **AgenticPay GlobalScore:** Aggregate welfare score
- **Buyer/Seller Surplus:** Economic efficiency

### Hallucination Types
1. **Format Failure:** Missing `### BUYER_PRICE($X) ###` tags
2. **Floor Violation:** Price < σ_j (seller floor)
3. **Phantom Concession:** Narrative price ≠ actual price
4. **Logic Error:** Invalid negotiation move

## 🔬 Research Context

This stress test suite validates the hypothesis from:

> **"Is Solo LLM just as good as grounded agents?"**
>
> Prior work (Fu et al., 2023; Abdelnabi et al., 2023) showed that grounding tools improve negotiation outcomes. This suite quantifies the performance gap across three dimensions: **deal rate**, **price efficiency**, and **hallucination rate**.

**Key Insight:** Solo LLM's 3.2× higher hallucination rate directly correlates with 20% lower deal rate and $350 higher average deal price (overpaying).

## 🛠️ Next Steps (Refinement Phase)

1. **Fix Tier 2 Anomaly:** Investigate Math Geek's unexpected 12% deal rate drop in Tier 2
2. **Increase Sample Size:** Scale from n=30 to n=100 for statistical significance
3. **Add Scenarios:** Implement time-pressure and information-asymmetry scenarios
4. **Cross-Validation:** Test with GPT-4 and Gemini Pro for model-agnostic results

## 📚 References

- Fu, J., et al. (2023). "Improving Language Model Negotiation with Self-Play and In-Context Learning from AI Feedback." *arXiv:2305.10142*
- Abdelnabi, S., et al. (2023). "LLM-Deliberation: Evaluating LLMs with Interactive Multi-Agent Negotiation Games." *arXiv:2309.17234*
- AgenticPay Algorithm 1: Temporal-discounted bilateral welfare scoring

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

This is a research project. For questions or collaboration:
- Open an issue on GitHub
- See [`STRESS_TEST_SPECIFICATION.md`](STRESS_TEST_SPECIFICATION.md) for implementation details
- Review [`STRESS_TEST_FINAL_ANALYSIS.md`](STRESS_TEST_FINAL_ANALYSIS.md) for current results

---

**Status:** ✅ Tier 1 Complete (n=30) | 🔄 Tier 2 In Progress (fixing anomaly)
