"""
Diagnostic script to analyze Tier 2 (Math Geek) formula behavior.

Tests the convergence formula against different buyer tactics to identify
why Tier 2 underperforms compared to Tier 1 and Tier 3.
"""

def calculate_optimal_guess_debug(
    current_round: int,
    buyer_last_offer: float,
    seller_floor: float,
    max_rounds: int = 10,
):
    """
    Debug version of calculate_optimal_guess with detailed output.
    Formula: P = (0.5 + 0.5 × t/tₘ) × B
    """
    t = min(current_round, max_rounds)
    convergence_factor = 0.5 + 0.5 * (t / max_rounds)
    convergence_pct = round(convergence_factor * 100, 1)
    raw_price = convergence_factor * buyer_last_offer
    floor_clamped = raw_price < seller_floor
    optimal_price = round(max(raw_price, seller_floor))

    return {
        "round": current_round,
        "buyer_offer": buyer_last_offer,
        "seller_floor": seller_floor,
        "convergence_factor": round(convergence_factor, 3),
        "convergence_pct": convergence_pct,
        "raw_price": round(raw_price, 2),
        "floor_clamped": floor_clamped,
        "optimal_price": optimal_price,
    }


def simulate_negotiation(
    buyer_initial_offer: float,
    buyer_increment: float,
    seller_floor: float,
    seller_initial_ask: float,
    max_rounds: int = 10,
):
    """
    Simulate a negotiation using the Math Geek formula.
    """
    print(f"\n{'='*80}")
    print(f"SIMULATION: Buyer starts at ${buyer_initial_offer}, "
          f"increments by ${buyer_increment}/round")
    print(f"Seller floor: ${seller_floor}, initial ask: ${seller_initial_ask}")
    print(f"{'='*80}\n")
    
    buyer_offer = buyer_initial_offer
    seller_ask = seller_initial_ask
    
    for rnd in range(1, max_rounds + 1):
        if rnd == 1:
            # Round 1: seller returns initial ask
            result = {
                "round": rnd,
                "buyer_offer": buyer_offer,
                "seller_floor": seller_floor,
                "convergence_factor": "N/A",
                "convergence_pct": "N/A",
                "raw_price": "N/A",
                "floor_clamped": False,
                "optimal_price": seller_initial_ask,
            }
        else:
            # Round 2+: use formula
            result = calculate_optimal_guess_debug(
                rnd, buyer_offer, seller_floor, max_rounds
            )
        
        seller_ask = result["optimal_price"]
        gap = seller_ask - buyer_offer
        
        print(f"Round {rnd}:")
        print(f"  Buyer offer:        ${buyer_offer:.2f}")
        print(f"  Seller counter:     ${seller_ask:.2f}")
        print(f"  Gap:                ${gap:.2f}")
        
        if rnd > 1:
            print(f"  Convergence factor: {result['convergence_factor']} "
                  f"({result['convergence_pct']}%)")
            print(f"  Raw formula price:  ${result['raw_price']:.2f}")
            print(f"  Floor clamped:      {result['floor_clamped']}")
        
        # Check if deal would close (gap < $15)
        if gap <= 15:
            print(f"\n  ✓ DEAL CLOSES at ${seller_ask:.2f} (gap: ${gap:.2f})")
            return seller_ask, rnd
        
        print()
        
        # Buyer increments offer for next round
        buyer_offer += buyer_increment
    
    print(f"  ✗ NO DEAL after {max_rounds} rounds")
    print(f"  Final gap: ${gap:.2f}")
    return None, max_rounds


def analyze_formula_vulnerability():
    """
    Test the formula against different buyer tactics.
    """
    print("\n" + "="*80)
    print("TIER 2 FORMULA VULNERABILITY ANALYSIS")
    print("="*80)
    
    # Tier configurations
    tier_configs = {
        "Tier 1 (Nova Kicks)": {"floor": 110, "ask": 180},
        "Tier 2 (SoleMaster)": {"floor": 125, "ask": 200},
        "Tier 3 (QuickShoe)": {"floor": 105, "ask": 165},
    }
    
    # Buyer tactics
    tactics = [
        {
            "name": "Aggressive Low-Ball",
            "initial": 100,
            "increment": 8,
            "desc": "Starts very low, slow increments"
        },
        {
            "name": "Moderate Anchoring",
            "initial": 120,
            "increment": 6,
            "desc": "Moderate start, steady increments"
        },
        {
            "name": "Fair Opening",
            "initial": 140,
            "increment": 4,
            "desc": "Reasonable start, small increments"
        },
    ]
    
    print("\n" + "="*80)
    print("KEY INSIGHT: Formula P = (0.5 + 0.5 × t/tₘ) × B")
    print("="*80)
    print("This formula converges TOWARD the buyer's offer, not toward a fair midpoint!")
    print("- At round 1: P = 0.5 × B (seller asks 50% of buyer offer)")
    print("- At round 10: P = 1.0 × B (seller asks 100% of buyer offer)")
    print("\nPROBLEM: If buyer starts low, formula forces seller to converge to LOW price!")
    print("="*80)
    
    for tactic in tactics:
        print(f"\n\n{'#'*80}")
        print(f"TACTIC: {tactic['name']}")
        print(f"Description: {tactic['desc']}")
        print(f"{'#'*80}")
        
        for tier_name, config in tier_configs.items():
            final_price, rounds = simulate_negotiation(
                buyer_initial_offer=tactic["initial"],
                buyer_increment=tactic["increment"],
                seller_floor=config["floor"],
                seller_initial_ask=config["ask"],
                max_rounds=10,
            )
            
            if final_price:
                margin = final_price - config["floor"]
                margin_pct = (margin / config["floor"]) * 100
                print(f"\n  {tier_name} RESULT:")
                print(f"    Final price: ${final_price:.2f}")
                print(f"    Margin: ${margin:.2f} ({margin_pct:.1f}% above floor)")
                print(f"    Rounds: {rounds}")


def test_formula_at_different_rounds():
    """
    Show how the formula behaves at different rounds with same buyer offer.
    """
    print("\n\n" + "="*80)
    print("FORMULA BEHAVIOR ACROSS ROUNDS (Fixed Buyer Offer = $130)")
    print("="*80)
    
    buyer_offer = 130
    seller_floor = 125
    
    print(f"\nBuyer offer: ${buyer_offer}")
    print(f"Seller floor: ${seller_floor}")
    print(f"\nFormula: P = (0.5 + 0.5 × t/10) × {buyer_offer}")
    print()
    
    for rnd in range(1, 11):
        result = calculate_optimal_guess_debug(rnd, buyer_offer, seller_floor, 10)
        print(f"Round {rnd:2d}: "
              f"Factor={result['convergence_factor']:.3f} → "
              f"Raw=${result['raw_price']:6.2f} → "
              f"Final=${result['optimal_price']:3.0f} "
              f"{'(FLOOR CLAMP)' if result['floor_clamped'] else ''}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("TIER 2 (MATH GEEK) DIAGNOSTIC ANALYSIS")
    print("="*80)
    
    # Test 1: Show formula behavior across rounds
    test_formula_at_different_rounds()
    
    # Test 2: Analyze vulnerability to buyer tactics
    analyze_formula_vulnerability()
    
    print("\n\n" + "="*80)
    print("DIAGNOSIS COMPLETE")
    print("="*80)
    print("\nROOT CAUSE IDENTIFIED:")
    print("  The formula P = (0.5 + 0.5 × t/tₘ) × B converges TOWARD the buyer's")
    print("  offer, not toward a fair midpoint between buyer and seller positions.")
    print("\n  This makes Tier 2 vulnerable to low-ball anchoring tactics:")
    print("  - If buyer starts at $100, formula pushes seller toward $100")
    print("  - Seller can only resist via floor price clamp")
    print("  - Higher floor ($125 vs $110/$105) means MORE rounds clamped")
    print("  - More rounds = lower efficiency score = lower composite score")
    print("\nRECOMMENDATION:")
    print("  Replace formula with one that considers BOTH buyer offer AND seller ask:")
    print("  P = (0.5 + 0.5 × t/tₘ) × (B + S) / 2")
    print("  This converges toward the MIDPOINT, not just the buyer's position.")
    print("="*80)
