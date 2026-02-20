"""
AgenticPay Bridge — integrates the vendored AgenticPay framework into the
Negotiation War Room.

Responsibilities:
  1. Bootstrap sys.path so `agenticpay.*` is importable from the vendor dir.
  2. Provide ClaudeHaikuLLM — a BaseLLM adapter that calls the Anthropic API.
  3. Expose AgenticPayScoringEngine — thin wrapper around the Algorithm 1
     formulas in Task1BasicPriceNegotiation (D=30, W=55, E=15, γ=0.99).
  4. Factory helpers for Task 1B-1P-1S (bilateral) and 1B-MP-MS (multi-product
     multi-seller) environments.
"""

from __future__ import annotations

import os
import re
import sys
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── 1. Bootstrap vendor path ──────────────────────────────────────────────────

_VENDOR = Path(__file__).parent / "vendor" / "AgenticPay"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

# ── 2. AgenticPay imports (available after path bootstrap) ─────────────────────

from agenticpay.models.base_llm import BaseLLM          # noqa: E402
from agenticpay.agents.base_agent import BaseAgent       # noqa: E402
from agenticpay.core import BaseEnv, NegotiationStatus   # noqa: E402
from agenticpay.envs.single_buyer_product_seller.Task1_basic_price_negotiation import (
    Task1BasicPriceNegotiation,
)                                                        # noqa: E402

# ── 3. Constants (Algorithm 1 defaults) ───────────────────────────────────────

GAMMA: float = 0.99
D: float = 30.0   # DealScore weight
W: float = 55.0   # QualityScore weight
E: float = 15.0   # EfficiencyScore weight
F: float = 15.0   # FailurePenalty weight

# Default sneaker negotiation reservation values (same domain as logic_engine)
DEFAULT_BUYER_MAX: float = 160.0   # buyer walks away above this
DEFAULT_SELLER_MIN: float = 110.0  # seller walks away below this
DEFAULT_INITIAL_PRICE: float = 185.0  # seller's opening ask


# ── 4. ClaudeHaikuLLM — BaseLLM adapter ──────────────────────────────────────

class ClaudeHaikuLLM(BaseLLM):
    """
    Anthropic claude-haiku-4-5 adapter implementing AgenticPay's BaseLLM.

    Uses the synchronous Anthropic client.  If ANTHROPIC_API_KEY is not set
    the adapter falls back to a scripted stub so the rest of the bridge can
    be imported and tested without an API key.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001", temperature: float = 0.7):
        self.model = model
        self.temperature = temperature
        self._client = None
        self._stub_mode = False

        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                self._stub_mode = True
            else:
                self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            self._stub_mode = True

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        if self._stub_mode:
            return self._stub_response(prompt)

        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens or 512,
            temperature=temperature or self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    # ------------------------------------------------------------------
    def _stub_response(self, prompt: str) -> str:
        """Deterministic stub used when no API key is available."""
        if "buyer" in prompt.lower():
            return "I'd like to propose ### BUYER_PRICE($145) ### for this product."
        return "I can offer ### SELLER_PRICE($155) ### as my best price."

    def __repr__(self) -> str:
        mode = "stub" if self._stub_mode else self.model
        return f"ClaudeHaikuLLM(model={mode})"


# ── 5. NegotiationAgent — BaseAgent concrete implementation ───────────────────

class NegotiationAgent(BaseAgent):
    """
    Concrete agent that wraps ClaudeHaikuLLM and formats prompts using
    the BaseAgent helper methods.

    role: "buyer" | "seller"
    """

    def __init__(
        self,
        llm: ClaudeHaikuLLM,
        role: str,
        name: str,
        extra_system: str = "",
    ):
        role_desc = (
            f"a negotiation {role} agent. Your goal is to reach the best "
            f"possible deal. Always include a price in the format "
            f"### {'BUYER' if role == 'buyer' else 'SELLER'}_PRICE($X) ###."
        )
        if extra_system:
            role_desc += f" {extra_system}"
        super().__init__(model=llm, role_description=role_desc, name=name)
        self.role = role

    def respond(
        self,
        conversation_history: List[Dict[str, Any]],
        current_state: Dict[str, Any],
    ) -> str:
        prompt = self._build_prompt(conversation_history, current_state)
        return self.model.generate(prompt, temperature=0.7, max_tokens=512)


# ── 6. Parser Π — price extraction (3 priority levels) ───────────────────────

_RE_LEVEL1_BUYER  = re.compile(r"###\s*BUYER_PRICE\(\$?([\d.]+)\)\s*###")
_RE_LEVEL1_SELLER = re.compile(r"###\s*SELLER_PRICE\(\$?([\d.]+)\)\s*###")
_RE_LEVEL2        = re.compile(r"###\s*\$?([\d.]+)\s*###")
_RE_LEVEL3_DOLLAR = re.compile(r"\$\s*([\d,.]+)")
_RE_LEVEL3_WORDS  = re.compile(r"([\d,.]+)\s*(?:dollars?|USD)", re.IGNORECASE)


def parse_price(text: str, role: str = "buyer") -> Optional[float]:
    """
    Parser Π: extract the proposed price from an agent utterance.

    Priority:
      1. ### BUYER_PRICE($X) ### / ### SELLER_PRICE($X) ###
      2. ### $X ###
      3. $X  or  X dollars/USD

    Returns None if no valid price is found (→ Price Overflow / invalid move).
    """
    # Level 1
    pat = _RE_LEVEL1_BUYER if role == "buyer" else _RE_LEVEL1_SELLER
    m = pat.search(text)
    if m:
        return float(m.group(1).replace(",", ""))

    # Level 2
    m = _RE_LEVEL2.search(text)
    if m:
        return float(m.group(1).replace(",", ""))

    # Level 3a — dollar sign
    m = _RE_LEVEL3_DOLLAR.search(text)
    if m:
        return float(m.group(1).replace(",", ""))

    # Level 3b — words
    m = _RE_LEVEL3_WORDS.search(text)
    if m:
        return float(m.group(1).replace(",", ""))

    return None


# ── 7. AgenticPayScoringEngine — Algorithm 1 implementation ──────────────────

class AgenticPayScoringEngine:
    """
    Pure-Python implementation of AgenticPay Algorithm 1.

    Scores are computed locally using the same formulas as
    Task1BasicPriceNegotiation, so we can score any negotiation without
    running the full environment.

    Default weights: D=30, W=55, E=15, F=15, γ=0.99
    """

    def __init__(
        self,
        gamma: float = GAMMA,
        d: float = D,
        w: float = W,
        e: float = E,
        f: float = F,
        buyer_max: float = DEFAULT_BUYER_MAX,
        seller_min: float = DEFAULT_SELLER_MIN,
    ):
        self.gamma = gamma
        self.d = d
        self.w = w
        self.e = e
        self.f = f
        self.buyer_max = buyer_max
        self.seller_min = seller_min

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _discount(self, round_index: int) -> float:
        return self.gamma ** round_index

    def _utility(self, price: float) -> Tuple[float, float]:
        """Returns (u_buyer, u_seller) ∈ [0,1]."""
        z = self.buyer_max - self.seller_min
        if z <= 0:
            return 0.0, 0.0
        u_b = max(0.0, min(1.0, (self.buyer_max - price) / z))
        u_s = max(0.0, min(1.0, (price - self.seller_min) / z))
        return u_b, u_s

    # ------------------------------------------------------------------
    # Score methods (Algorithm 1)
    # ------------------------------------------------------------------

    def global_score(self, price: float, round_index: int, success: bool) -> float:
        disc = self._discount(round_index)
        if success:
            u_b, u_s = self._utility(price)
            q = 4 * u_b * u_s          # quality factor ∈ [0,1]
            return self.d * disc + self.w * q * disc + self.e * disc
        return -self.f * (1 - disc)

    def buyer_score(self, price: float, round_index: int, success: bool) -> float:
        disc = self._discount(round_index)
        if success:
            u_b, _ = self._utility(price)
            return disc * (self.d + self.w * u_b + self.e)
        return -self.f * (1 - disc)

    def seller_score(self, price: float, round_index: int, success: bool) -> float:
        disc = self._discount(round_index)
        if success:
            _, u_s = self._utility(price)
            return disc * (self.d + self.w * u_s + self.e)
        return -self.f * (1 - disc)

    def score_bundle(
        self,
        price: float,
        round_index: int,
        success: bool,
    ) -> Dict[str, float]:
        """Return all three scores in one call."""
        return {
            "global_score": round(self.global_score(price, round_index, success), 3),
            "buyer_score": round(self.buyer_score(price, round_index, success), 3),
            "seller_score": round(self.seller_score(price, round_index, success), 3),
            "discount": round(self._discount(round_index), 4),
            "round_index": round_index,
            "success": success,
            "price": price,
        }


# ── 8. Environment factories ───────────────────────────────────────────────────

def make_task_1b1p1s(
    buyer_llm: Optional[ClaudeHaikuLLM] = None,
    seller_llm: Optional[ClaudeHaikuLLM] = None,
    buyer_max: float = DEFAULT_BUYER_MAX,
    seller_min: float = DEFAULT_SELLER_MIN,
    initial_price: float = DEFAULT_INITIAL_PRICE,
    max_rounds: int = 10,
) -> Task1BasicPriceNegotiation:
    """
    Task 1B-1P-1S — Bilateral Bargaining (1 Buyer, 1 Product, 1 Seller).

    Returns a ready-to-reset Task1BasicPriceNegotiation environment.
    """
    buyer_llm = buyer_llm or ClaudeHaikuLLM()
    seller_llm = seller_llm or ClaudeHaikuLLM()

    buyer_agent = NegotiationAgent(buyer_llm, "buyer", "Buyer")
    seller_agent = NegotiationAgent(seller_llm, "seller", "Seller")

    return Task1BasicPriceNegotiation(
        buyer_agent=buyer_agent,
        seller_agent=seller_agent,
        max_rounds=max_rounds,
        initial_seller_price=initial_price,
        buyer_max_price=buyer_max,
        seller_min_price=seller_min,
        gamma=GAMMA,
        deal_score_weight=D,
        quality_score_weight=W,
        efficiency_score_weight=E,
        failure_penalty_weight=F,
        buyer_deal_weight=D,
        buyer_utility_weight=W,
        buyer_efficiency_weight=E,
        buyer_failure_penalty_weight=F,
        seller_deal_weight=D,
        seller_utility_weight=W,
        seller_efficiency_weight=E,
        seller_failure_penalty_weight=F,
    )


def make_task_1b_mp_ms(
    n_products: int = 2,
    n_sellers: int = 2,
    buyer_llm: Optional[ClaudeHaikuLLM] = None,
    seller_llm: Optional[ClaudeHaikuLLM] = None,
    buyer_max: float = DEFAULT_BUYER_MAX,
    seller_min: float = DEFAULT_SELLER_MIN,
    initial_price: float = DEFAULT_INITIAL_PRICE,
    max_rounds: int = 10,
) -> List[Task1BasicPriceNegotiation]:
    """
    Task 1B-MP-MS — Multi-Product Multi-Seller (1 Buyer, M Products, S Sellers).

    Returns a list of Task1BasicPriceNegotiation environments, one per
    (product, seller) pair.  The buyer LLM is shared across all pairs.
    """
    buyer_llm = buyer_llm or ClaudeHaikuLLM()
    envs = []
    for seller_idx in range(n_sellers):
        for product_idx in range(n_products):
            s_llm = seller_llm or ClaudeHaikuLLM()
            buyer_agent = NegotiationAgent(buyer_llm, "buyer", f"Buyer")
            seller_agent = NegotiationAgent(s_llm, "seller", f"Seller_{seller_idx+1}")
            env = Task1BasicPriceNegotiation(
                buyer_agent=buyer_agent,
                seller_agent=seller_agent,
                max_rounds=max_rounds,
                initial_seller_price=initial_price + seller_idx * 5,
                buyer_max_price=buyer_max,
                seller_min_price=seller_min,
                gamma=GAMMA,
                deal_score_weight=D,
                quality_score_weight=W,
                efficiency_score_weight=E,
                failure_penalty_weight=F,
                buyer_deal_weight=D,
                buyer_utility_weight=W,
                buyer_efficiency_weight=E,
                buyer_failure_penalty_weight=F,
                seller_deal_weight=D,
                seller_utility_weight=W,
                seller_efficiency_weight=E,
                seller_failure_penalty_weight=F,
                environment_info={"product_index": product_idx, "seller_index": seller_idx},
            )
            envs.append(env)
    return envs


# ── 9. Smoke test ──────────────────────────────────────────────────────────────

def _smoke_test() -> None:
    """Quick sanity check — run a 1-round stub negotiation and print scores."""
    engine = AgenticPayScoringEngine()

    # Bilateral deal at $140 (round 3, success)
    scores = engine.score_bundle(price=140.0, round_index=3, success=True)
    print("[smoke] Task 1B-1P-1S scores:", scores)

    # Failed deal (timeout at round 10)
    fail = engine.score_bundle(price=0.0, round_index=10, success=False)
    print("[smoke] Failed negotiation scores:", fail)

    # Parser Π test
    sample = "After consideration, ### BUYER_PRICE($142.50) ### is my final offer."
    price = parse_price(sample, role="buyer")
    print(f"[smoke] Parser Π extracted: ${price}")

    print("[smoke] Bridge OK")


if __name__ == "__main__":
    _smoke_test()
