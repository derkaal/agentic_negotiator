"""
Seller agent nodes for the LangGraph negotiation graph.

Three tiers — all start at COMMON_STARTING_PRICE:

  Tier 1 — Solo LLM
      No tools.  Pure LLM judgment.  Can drift, hallucinate prices, be
      manipulated by the buyer's framing.

  Tier 2 — Math-Grounded
      Calls boulware_calculator first (Python, no LLM).  The resulting
      must_offer_exactly price is injected into the system prompt so the
      LLM can only paraphrase it, never change it.

  Tier 3 — Probing + Math
      Full tool-calling agent.  Has access to both ask_buyer_question
      (T3-only) and boulware_calculator.  Runs its own inner ReAct loop,
      then produces a final offer that combines buyer intel with math.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ..state import (
    COMMON_FLOOR,
    COMMON_STARTING_PRICE,
    MARKET_AVG_PRICE,
    MAX_ROUNDS,
    NegotiationState,
)
from ..tools import boulware_fn, boulware_calculator

# ── Shared LLM instances ──────────────────────────────────────────────────────

_LLM_CREATIVE = ChatAnthropic(
    model="claude-haiku-4-5-20251001", temperature=0.7, max_tokens=300
)
_LLM_PRECISE = ChatAnthropic(
    model="claude-haiku-4-5-20251001", temperature=0.2, max_tokens=300
)
_LLM_BALANCED = ChatAnthropic(
    model="claude-haiku-4-5-20251001", temperature=0.4, max_tokens=400
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_price(text: str) -> Optional[float]:
    """Pull the first dollar amount from a message string."""
    matches = re.findall(r"\$\s*([\d,]+(?:\.\d{1,2})?)", text)
    if matches:
        return float(matches[0].replace(",", ""))
    matches = re.findall(r"\b(1[0-9]{2}(?:\.\d{1,2})?)\b", text)
    if matches:
        return float(matches[0])
    return None


# ── Tier 1 — Solo LLM ─────────────────────────────────────────────────────────

def make_seller_t1() -> Callable[[NegotiationState], dict]:
    """
    Tier 1: bare LLM, no tools, no math grounding.
    The agent decides prices entirely from its own language-model judgment.
    """
    system = SystemMessage(content=f"""\
You are a seller negotiating the price of a pair of sneakers.

Context:
- Your opening ask: ${COMMON_STARTING_PRICE:.2f}
- Market average price: ${MARKET_AVG_PRICE:.2f} (public knowledge)
- Your floor price: CONFIDENTIAL — never reveal it
- Max rounds: {MAX_ROUNDS}

Rules:
- Every response must include a clear dollar price offer, formatted as $XXX.XX
- Be firm but willing to concede as rounds progress
- Respond in 2-3 sentences: state your price and give a short justification
- Do NOT accept below your costs (use your judgment about a reasonable floor)
""")

    def seller_t1_node(state: NegotiationState) -> dict:
        rnd = state["round"]
        messages = [system] + state["messages"]

        # Prepend a round-context reminder
        messages.append(HumanMessage(
            content=f"[SYSTEM] Round {rnd}/{state['max_rounds']}. Make your offer."
        ))

        response = _LLM_CREATIVE.invoke(messages)
        price = _extract_price(response.content)

        return {
            "messages":      [response],
            "current_offer": price,
        }

    return seller_t1_node


# ── Tier 2 — Math-Grounded ────────────────────────────────────────────────────

def make_seller_t2() -> Callable[[NegotiationState], dict]:
    """
    Tier 2: Boulware math is computed first in Python; the LLM's only job
    is to communicate the result.  The price cannot drift from the formula.
    """

    def seller_t2_node(state: NegotiationState) -> dict:
        rnd          = state["round"]
        buyer_counter = state.get("buyer_counter") or 0.0

        # ── Step 1: deterministic price from Boulware formula ────────────────
        math_result = boulware_fn(
            current_round  = rnd,
            buyer_counter  = buyer_counter,
            floor          = COMMON_FLOOR,
            starting_price = COMMON_STARTING_PRICE,
            max_rounds     = state["max_rounds"],
        )
        must_price = math_result["must_offer_exactly"]

        # ── Step 2: LLM formats the message (price is already fixed) ─────────
        system = SystemMessage(content=f"""\
You are a seller negotiating the price of sneakers.

The Boulware pricing engine has calculated your offer for round {rnd}: \
${must_price:.2f}

You MUST quote exactly ${must_price:.2f} — no higher, no lower.
Your job is only to communicate this price naturally in 1-2 sentences.
Include the exact figure "${ must_price:.2f}" in your response.
""")

        messages = [system] + state["messages"]
        response = _LLM_PRECISE.invoke(messages)

        # Ensure price is in the message even if LLM forgets
        if f"${must_price:.2f}" not in response.content:
            patched = AIMessage(
                content=f"My offer for round {rnd} is ${must_price:.2f}. "
                        + response.content
            )
        else:
            patched = response

        return {
            "messages":      [patched],
            "current_offer": must_price,
        }

    return seller_t2_node


# ── Tier 3 — Probing + Math ───────────────────────────────────────────────────

def make_seller_t3(ask_buyer_question_tool) -> Callable[[NegotiationState], dict]:
    """
    Tier 3: full tool-calling agent.  On each turn it:
      1. Optionally calls ask_buyer_question (rounds 1-2, or after a rejection)
      2. Calls boulware_calculator to anchor the price
      3. Produces a final offer that combines buyer intel + math result

    ask_buyer_question_tool is the buyer-type-specific tool created by
    make_ask_buyer_question_tool() in tools.py.
    """
    tools = [boulware_calculator, ask_buyer_question_tool]
    llm_with_tools = _LLM_BALANCED.bind_tools(tools)

    system_tpl = """\
You are a Tier 3 seller — a probing strategist with two tools:

  1. ask_buyer_question(question)  — ask the buyer why they rejected or what
     they prioritise (price / warranty / delivery). Use this in rounds 1-2 or
     immediately after a rejection.
  2. boulware_calculator(current_round, buyer_counter, floor, starting_price,
     max_rounds) — returns the mathematically optimal price. You MUST call this
     every turn and anchor your final offer to its "must_offer_exactly" value.

Current state:
  Round:                {rnd}/{max_rounds}
  Starting price:       ${starting_price:.2f}
  Floor:                CONFIDENTIAL
  Buyer's last counter: {buyer_counter}
  Buyer intel so far:   {buyer_intel}

Strategy:
  - Rounds 1-2: call ask_buyer_question first, then boulware_calculator.
    Use the buyer's answer to frame your offer (warranty / delivery language)
    but keep the price at the boulware result.
  - Round 3+: call boulware_calculator only (unless you just got a rejection).
  - NEVER offer below ${floor:.2f}.
  - Your final message must contain your price as $XXX.XX.
"""

    def seller_t3_node(state: NegotiationState) -> dict:
        rnd           = state["round"]
        buyer_counter = state.get("buyer_counter") or 0.0
        buyer_intel   = state.get("buyer_preferences_revealed") or {}
        intel_str     = (
            "; ".join(f"{k}: {v}" for k, v in buyer_intel.items())
            if buyer_intel else "none yet"
        )

        system = SystemMessage(content=system_tpl.format(
            rnd            = rnd,
            max_rounds     = state["max_rounds"],
            starting_price = COMMON_STARTING_PRICE,
            floor          = COMMON_FLOOR,
            buyer_counter  = f"${buyer_counter:.2f}" if buyer_counter else "none",
            buyer_intel    = intel_str,
        ))

        messages      = [system] + state["messages"]
        new_messages  = []
        buyer_prefs   = dict(buyer_intel)  # local copy to accumulate answers

        # ── Inner ReAct loop (max 4 iterations) ──────────────────────────────
        for _ in range(4):
            response = llm_with_tools.invoke(messages + new_messages)
            new_messages.append(response)

            if not response.tool_calls:
                break   # agent produced its final answer

            tool_results = []
            for tc in response.tool_calls:
                name = tc["name"]
                args = tc["args"]

                if name == "boulware_calculator":
                    # Always inject current state values
                    args.setdefault("current_round",  rnd)
                    args.setdefault("buyer_counter",  buyer_counter)
                    args.setdefault("floor",          COMMON_FLOOR)
                    args.setdefault("starting_price", COMMON_STARTING_PRICE)
                    args.setdefault("max_rounds",     state["max_rounds"])
                    result = boulware_calculator.invoke(args)
                    tool_results.append(ToolMessage(
                        content     = str(result),
                        tool_call_id= tc["id"],
                        name        = name,
                    ))

                elif name == "ask_buyer_question":
                    answer = ask_buyer_question_tool.invoke(args)
                    # Accumulate buyer intelligence
                    buyer_prefs[args.get("question", "q")] = answer
                    tool_results.append(ToolMessage(
                        content     = answer,
                        tool_call_id= tc["id"],
                        name        = name,
                    ))

            new_messages.extend(tool_results)

        # Extract final offer price from last AI message
        last_ai = next(
            (m for m in reversed(new_messages) if isinstance(m, AIMessage)), None
        )
        price = _extract_price(last_ai.content) if last_ai else None

        return {
            "messages":                   new_messages,
            "current_offer":              price,
            "buyer_preferences_revealed": buyer_prefs,
        }

    return seller_t3_node
