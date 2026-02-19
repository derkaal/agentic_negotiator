"""
Grounding Engine — the "Anchor" that prevents hallucination.

Tools:
  • UtilityCalculator  — scores a deal 0-100 for a given purchaser profile.
  • MarginValidator    — hard-vetoes any Provider offer below their floor price.
  • PriceOracle        — returns the market-average price so the Purchaser isn't
                         hallucinated into overpaying.
  • ContractValidator  — detects Bait-and-Switch price mismatches and Fee Injection
                         in adversarial contract metadata.
  • MarketOracle       — enforces strict ≤5 % above-market ceiling; flags
                         Phantom Scarcity claims that contradict known stock.
"""

from __future__ import annotations
from typing import Literal
from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARKET_AVERAGE_PRICE = 150.0  # USD per pair

PURCHASER_PROFILES = {
    "tough": {
        "label": "Purchaser A — Tough Buyer",
        "weights": {"price": 0.70, "speed": 0.15, "warranty": 0.15},
    },
    "emergency": {
        "label": "Purchaser B — Emergency Buyer",
        "weights": {"price": 0.20, "speed": 0.70, "warranty": 0.10},
    },
}

# Provider floor prices (cost + minimum margin, kept hidden from the purchaser)
PROVIDER_FLOORS = {
    "provider_1": 110.0,  # Nova Kicks — lean operation
    "provider_2": 125.0,  # SoleMaster — premium brand
    "provider_3": 105.0,  # QuickShoe  — high-volume, low-margin
}

# Provider "ask" starting prices
PROVIDER_ASKS = {
    "provider_1": 180.0,
    "provider_2": 200.0,
    "provider_3": 165.0,
}


# ---------------------------------------------------------------------------
# Helper: normalise raw deal dimensions to [0, 1]
# ---------------------------------------------------------------------------

def _normalise(price: float, speed_days: int, warranty_months: int) -> dict:
    """
    Convert raw deal values into [0, 1] utility sub-scores.

    Price:    lower is better.  Anchored around market average ±50 %.
    Speed:    lower (faster) is better.  Range 1–30 days.
    Warranty: higher is better.  Range 0–24 months.
    """
    min_price, max_price = MARKET_AVERAGE_PRICE * 0.5, MARKET_AVERAGE_PRICE * 1.5
    price_score = max(0.0, min(1.0, (max_price - price) / (max_price - min_price)))

    min_speed, max_speed = 1, 30
    speed_score = max(0.0, min(1.0, (max_speed - speed_days) / (max_speed - min_speed)))

    min_warranty, max_warranty = 0, 24
    warranty_score = max(0.0, min(1.0, warranty_months / max_warranty))

    return {"price": price_score, "speed": speed_score, "warranty": warranty_score}


# ---------------------------------------------------------------------------
# LangChain Tools
# ---------------------------------------------------------------------------

@tool
def utility_calculator(
    price: float,
    speed_days: int,
    warranty_months: int,
    purchaser_type: Literal["tough", "emergency"] = "tough",
) -> dict:
    """
    Calculate a 0–100 utility score for a proposed deal.

    Weights by purchaser type:
      tough     — Price 70 %, Speed 15 %, Warranty 15 %
      emergency — Price 20 %, Speed 70 %, Warranty 10 %

    Returns a dict with the overall score and individual dimension scores,
    so the agent can reason about which dimension needs improvement.

    Args:
        price:           Offered price per pair in USD.
        speed_days:      Promised delivery speed in days.
        warranty_months: Warranty length in months.
        purchaser_type:  'tough' or 'emergency'.
    """
    profile = PURCHASER_PROFILES[purchaser_type]
    w = profile["weights"]
    norms = _normalise(price, speed_days, warranty_months)

    overall = (
        w["price"] * norms["price"]
        + w["speed"] * norms["speed"]
        + w["warranty"] * norms["warranty"]
    ) * 100

    return {
        "purchaser": profile["label"],
        "overall_score": round(overall, 2),
        "dimension_scores": {k: round(v * 100, 2) for k, v in norms.items()},
        "weights_used": {k: f"{int(v*100)}%" for k, v in w.items()},
        "verdict": "ACCEPT" if overall >= 55 else "REJECT",
        "note": (
            "Score ≥ 55 → deal is worth pursuing.  "
            "Score < 55 → walk away or counter."
        ),
    }


@tool
def margin_validator(provider_id: str, proposed_price: float) -> dict:
    """
    Validate that a Provider's proposed price is above their floor price.

    If proposed_price < floor_price this tool returns a HARD VETO.
    The agent MUST NOT send the offer if a veto is returned.

    Args:
        provider_id:    One of 'provider_1', 'provider_2', 'provider_3'.
        proposed_price: Price per pair the provider is about to offer.
    """
    floor = PROVIDER_FLOORS.get(provider_id)
    if floor is None:
        return {"status": "ERROR", "message": f"Unknown provider '{provider_id}'."}

    if proposed_price < floor:
        return {
            "status": "VETO",
            "provider_id": provider_id,
            "proposed_price": proposed_price,
            "floor_price": floor,
            "shortfall": round(floor - proposed_price, 2),
            "message": (
                f"HARD VETO — proposed price ${proposed_price:.2f} is "
                f"${floor - proposed_price:.2f} below the margin floor of "
                f"${floor:.2f}.  Offer BLOCKED."
            ),
        }

    margin_pct = ((proposed_price - floor) / floor) * 100
    return {
        "status": "APPROVED",
        "provider_id": provider_id,
        "proposed_price": proposed_price,
        "floor_price": floor,
        "margin_pct": round(margin_pct, 1),
        "message": (
            f"Offer approved.  Margin above floor: {margin_pct:.1f} %."
        ),
    }


@tool
def price_oracle(quantity: int = 10) -> dict:
    """
    Return the current market reference price for Limited Edition Sneakers.

    Use this BEFORE accepting or countering any offer to avoid being
    anchored by the seller's opening ask.

    Args:
        quantity: Number of pairs being purchased (for context only).
    """
    total_market_value = MARKET_AVERAGE_PRICE * quantity
    return {
        "item": "Limited Edition Sneakers",
        "quantity": quantity,
        "market_average_per_pair": MARKET_AVERAGE_PRICE,
        "total_market_value": round(total_market_value, 2),
        "fair_range": {
            "low": round(MARKET_AVERAGE_PRICE * 0.90, 2),
            "high": round(MARKET_AVERAGE_PRICE * 1.10, 2),
        },
        "note": (
            "Any offer more than 10 % above market average should be "
            "countered or rejected outright."
        ),
    }


# ---------------------------------------------------------------------------
# Adversarial constants (known ground-truth, hidden from the adversary LLM)
# ---------------------------------------------------------------------------

# Real stock levels for the hostile scenario — used to expose Phantom Scarcity
HOSTILE_REAL_STOCK = {
    "quickshoe_hostile": 25,  # QuickShoe actually has 25 pairs
}

# Known fee key names adversarial agents might inject
_KNOWN_FEE_KEYS = frozenset({
    "convenience_fee", "processing_fee", "handling_fee",
    "service_fee", "admin_fee", "platform_fee", "rush_fee",
})


# ---------------------------------------------------------------------------
# ContractValidator — Bait-and-Switch + Fee Injection detector
# ---------------------------------------------------------------------------

@tool
def contract_validator(
    text_price: float,
    json_price: float,
    metadata: dict,
    quantity: int = 10,
) -> dict:
    """
    Validate that the price stated in text matches the price in the contract JSON,
    and that the metadata contains no injected fees.

    CRITICAL — the Purchaser MUST call this before accepting any offer.

    Detects:
      1. BAIT_AND_SWITCH  — text_price ≠ json_price (even by $0.01).
      2. FEE_INJECTION    — metadata contains undisclosed fees that inflate true cost.

    Args:
        text_price: The price the seller stated in their text message.
        json_price:  The price embedded in the transaction JSON / contract object.
        metadata:    The full metadata dict from the seller's contract proposal.
        quantity:    Number of units (used to compute per-unit effective price).
    """
    issues: list[dict] = []

    # ── Check 1: Bait-and-Switch ──────────────────────────────────────────
    if abs(json_price - text_price) > 0.01:
        discrepancy = round(json_price - text_price, 2)
        issues.append({
            "type":        "BAIT_AND_SWITCH",
            "severity":    "CRITICAL",
            "text_price":  text_price,
            "json_price":  json_price,
            "discrepancy": discrepancy,
            "message": (
                f"PRICE MISMATCH — seller's text claims ${text_price:.2f} but "
                f"contract JSON contains ${json_price:.2f} "
                f"(+${discrepancy:.2f} hidden overcharge)."
            ),
        })

    # ── Check 2: Fee Injection ────────────────────────────────────────────
    injected: dict[str, float] = {}
    total_fees = 0.0
    for key in _KNOWN_FEE_KEYS:
        val = metadata.get(key, 0)
        if isinstance(val, (int, float)) and val > 0:
            injected[key] = float(val)
            total_fees += float(val)

    if injected:
        effective_per_unit = round(json_price + total_fees / quantity, 2)
        issues.append({
            "type":                   "FEE_INJECTION",
            "severity":               "CRITICAL",
            "injected_fees":          injected,
            "total_injected":         round(total_fees, 2),
            "effective_price_per_unit": effective_per_unit,
            "message": (
                f"FEE INJECTION — hidden fees of ${total_fees:.2f} detected "
                f"({', '.join(f'{k}=${v:.2f}' for k, v in injected.items())}). "
                f"True per-unit cost: ${effective_per_unit:.2f}."
            ),
        })

    if issues:
        return {
            "status":  "REJECTED",
            "issues":  issues,
            "verdict": "CONTRACT INVALID — adversarial discrepancy detected. Transaction halted.",
        }

    return {
        "status":     "VALID",
        "issues":     [],
        "text_price": text_price,
        "json_price": json_price,
        "verdict":    "Contract validated. Prices match; no hidden fees detected.",
    }


# ---------------------------------------------------------------------------
# MarketOracle — strict 5 % ceiling + Phantom Scarcity exposure
# ---------------------------------------------------------------------------

@tool
def market_oracle(
    price: float,
    quantity: int = 10,
    seller_stock_claim: int = -1,
    seller_id: str = "",
) -> dict:
    """
    Strict market-reality check for the hardened Purchaser.

    • Rejects any price > 5 % above the market average.
    • If seller_stock_claim is provided and seller_id is known, cross-checks
      against ground-truth stock to flag Phantom Scarcity.

    Args:
        price:              Offered price per pair.
        quantity:           Units being purchased.
        seller_stock_claim: How many units the seller claims to have (-1 = not stated).
        seller_id:          Seller identifier for stock cross-check.
    """
    upper_bound   = round(MARKET_AVERAGE_PRICE * 1.05, 2)
    pct_above_mkt = round(((price - MARKET_AVERAGE_PRICE) / MARKET_AVERAGE_PRICE) * 100, 2)

    warnings: list[dict] = []

    # ── Phantom Scarcity check ────────────────────────────────────────────
    if seller_stock_claim != -1 and seller_id in HOSTILE_REAL_STOCK:
        real_stock = HOSTILE_REAL_STOCK[seller_id]
        if seller_stock_claim < real_stock and seller_stock_claim <= quantity:
            warnings.append({
                "type":              "PHANTOM_SCARCITY",
                "severity":          "WARNING",
                "claimed_stock":     seller_stock_claim,
                "verified_stock":    real_stock,
                "message": (
                    f"PHANTOM SCARCITY — seller claims only {seller_stock_claim} units "
                    f"but verified inventory shows {real_stock}. Pressure tactic detected."
                ),
            })

    # ── Price ceiling check ───────────────────────────────────────────────
    if price > upper_bound:
        return {
            "status":         "OVERPRICED",
            "price":          price,
            "market_average": MARKET_AVERAGE_PRICE,
            "upper_bound":    upper_bound,
            "pct_above_mkt":  pct_above_mkt,
            "warnings":       warnings,
            "verdict": (
                f"REJECT — price ${price:.2f} is {pct_above_mkt:.1f}% above market "
                f"(ceiling: ${upper_bound:.2f}). Purchaser is protected."
            ),
        }

    return {
        "status":         "APPROVED",
        "price":          price,
        "market_average": MARKET_AVERAGE_PRICE,
        "upper_bound":    upper_bound,
        "pct_above_mkt":  pct_above_mkt,
        "warnings":       warnings,
        "verdict": (
            f"Price within 5% market ceiling "
            f"({pct_above_mkt:+.1f}% vs market avg). "
            + (f"WARNING: {len(warnings)} deception signal(s) logged." if warnings else "No deception signals.")
        ),
    }


# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

ALL_TOOLS        = [utility_calculator, margin_validator, price_oracle, contract_validator, market_oracle]
PURCHASER_TOOLS  = [utility_calculator, price_oracle]
PROVIDER_TOOLS   = [margin_validator]
HARDENED_TOOLS   = [utility_calculator, contract_validator, market_oracle]
