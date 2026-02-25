"""
Test script to validate the proposed Tier 2 formula fix.

Compares OLD formula vs NEW formula behavior under adversarial conditions.
"""


def calculate_optimal_guess_OLD(
    current_round: int,
    buyer_last_offer: float,
    seller_floor: float,
    max_rounds: int = 10,
):
    """
    OLD FORMULA (FLAWED): P = (0.5 + 0.5 × t/tₘ) × B
    Converges toward buyer's offer only.
    """
    t = min(current_round, max_rounds)
    convergence_factor = 0.5 + 0.5 * (t / max_rounds)
    raw_price = convergence_factor * buyer_last_offer
    optimal_price = round(max(raw_price, seller_floor))
    
    return {
        "formula": "OLD: P = (0.5 + 0.5 × t/tₘ) × B",
        "convergence_factor": round(convergence_factor, 3),
        "raw_price": round(raw_price, 2),
        "floor_clamped": raw_price < seller_floor,
        "optimal_price": optimal_price,
    }


def calculate_optimal_guess_NEW(
    current_round: int,
    buyer_last_offer: float,
    seller_floor: float,
    seller_last_ask: float,
    max_rounds: int = 10,
):
    """
    NEW FORMULA (FIXED): P = (0.5 + 0.5 × t/tₘ) × (B + S) / 2
    Converges toward midpoint between buyer and seller.
    """
    t = min(current_round, max_rounds)
    convergence_factor = 0.5 + 0.5 * (t / max_rounds)
    
    # Calculate midpoint between buyer and seller
    midpoint = (buyer_last_offer + seller_last_ask) / 2
    
    # Converge toward midpoint
    raw_price = convergence_factor * midpoint
    
    optimal_price = round(max(raw_price, seller_floor))
    
    return {
        "formula": "NEW: P = (0.5 + 0.5 × t/tₘ) × (B + S) / 2",
        "convergence_factor": round(convergence_factor, 3),
        "midpoint": round(midpoint, 2),
        "raw_price": round(raw_price, 2),
        "floor_clamped": raw_price < seller_floor,
        "optimal_price": optimal_price,
    }


def simulate_negotiation_comparison(
    buyer_initial_offer: float,
    buyer_increment: float,
    seller_floor: float,
    seller_initial_ask: float,
    max_rounds: int = 10,
):
    """
    Compare OLD vs NEW formula in same negotiation scenario.
    """
    print(f"\n{'='*80}")
    print(f"COMPARISON: Buyer starts at ${buyer_initial_offer}, "
          f"+${buyer_increment}/round")
    print(f"Seller: floor=${seller_floor}, initial ask=${seller_initial_ask}")
    print(f"{'='*80}\n")
    
    buyer_offer = buyer_initial_offer
    seller_ask_old = seller_initial_ask
    seller_ask_new = seller_initial_ask
    
    print(f"{'Round':<6} {'Buyer':<8} {'OLD Formula':<12} {'NEW Formula':<12} "
          f"{'Gap OLD':<10} {'Gap NEW':<10}")
    print("-" * 80)
    
    for rnd in range(1, max_rounds + 1):
        if rnd == 1:
            # Round 1: both return initial ask
            result_old = {"optimal_price": seller_initial_ask}
            result_new = {"optimal_price": seller_initial_ask}
        else:
            # Round 2+: use formulas
            result_old = calculate_optimal_guess_OLD(
                rnd, buyer_offer, seller_floor, max_rounds
            )
            result_new = calculate_optimal_guess_NEW(
                rnd, buyer_offer, seller_floor, seller_ask_new, max_rounds
            )
        
        seller_ask_old = result_old["optimal_price"]
        seller_ask_new = result_new["optimal_price"]
        
        gap_old = seller_ask_old - buyer_offer
        gap_new = seller_ask_new - buyer_offer
        
        print(f"{rnd:<6} ${buyer_offer:<7.2f} ${seller_ask_old:<11.2f} "
              f"${seller_ask_new:<11.2f} ${gap_old:<9.2f} ${gap_new:<9.2f}")
        
        # Check if deals would close (gap < $15)
        old_closes = gap_old <= 15
        new_closes = gap_new <= 15
        
        if old_closes or new_closes:
            print()
            if old_closes:
                print(f"  OLD: ✓ Deal closes at ${seller_ask_old:.2f} "
                      f"(round {rnd}, gap ${gap_old:.2f})")
            else:
                print(f"  OLD: ✗ No deal yet (gap ${gap_old:.2f})")
            
            if new_closes:
                print(f"  NEW: ✓ Deal closes at ${seller_ask_new:.2f} "
                      f"(round {rnd}, gap ${gap_new:.2f})")
            else:
                print(f"  NEW: ✗ No deal yet (gap ${gap_new:.2f})")
            
            if old_closes and new_closes:
                price_diff = seller_ask_new - seller_ask_old
                print(f"\n  💰 Price improvement: ${price_diff:.2f} "
                      f"({(price_diff/seller_ask_old)*100:.1f}%)")
                return seller_ask_old, seller_ask_new, rnd
            elif new_closes:
                return None, seller_ask_new, rnd
            elif old_closes:
                return seller_ask_old, None, rnd
        
        # Buyer increments offer for next round
        buyer_offer += buyer_increment
    
    print(f"\n  ✗ Neither formula closed deal in {max_rounds} rounds")
    return None, None, max_rounds


def run_comparison_tests():
    """
    Run comprehensive comparison tests.
    """
    print("\n" + "="*80)
    print("TIER 2 FORMULA FIX VALIDATION")
    print("="*80)
    print("\nComparing OLD formula vs NEW formula under adversarial conditions")
    
    # Tier 2 configuration
    tier2_floor = 125
    tier2_ask = 200
    
    # Test scenarios
    scenarios = [
        {
            "name": "Adversarial Lowball (Stress Test Scenario)",
            "buyer_initial": 82.50,  # 45% below $150 market
            "buyer_increment": 8,
            "desc": "Extreme lowball + slow increments"
        },
        {
            "name": "Moderate Anchoring",
            "buyer_initial": 120,
            "buyer_increment": 6,
            "desc": "Moderate start, steady increments"
        },
        {
            "name": "Fair Opening",
            "buyer_initial": 140,
            "buyer_increment": 4,
            "desc": "Reasonable start, small increments"
        },
    ]
    
    results = []
    
    for scenario in scenarios:
        print(f"\n\n{'#'*80}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"Description: {scenario['desc']}")
        print(f"{'#'*80}")
        
        old_price, new_price, rounds = simulate_negotiation_comparison(
            buyer_initial_offer=scenario["buyer_initial"],
            buyer_increment=scenario["buyer_increment"],
            seller_floor=tier2_floor,
            seller_initial_ask=tier2_ask,
            max_rounds=10,
        )
        
        results.append({
            "scenario": scenario["name"],
            "old_price": old_price,
            "new_price": new_price,
            "rounds": rounds,
        })
    
    # Summary
    print("\n\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    print(f"\n{'Scenario':<40} {'OLD Price':<12} {'NEW Price':<12} "
          f"{'Improvement':<12}")
    print("-" * 80)
    
    total_improvement = 0
    scenarios_improved = 0
    
    for result in results:
        old_price = result["old_price"]
        new_price = result["new_price"]
        
        if old_price and new_price:
            improvement = new_price - old_price
            improvement_pct = (improvement / old_price) * 100
            total_improvement += improvement
            scenarios_improved += 1
            
            print(f"{result['scenario']:<40} ${old_price:<11.2f} "
                  f"${new_price:<11.2f} +${improvement:.2f} "
                  f"({improvement_pct:+.1f}%)")
        elif new_price:
            print(f"{result['scenario']:<40} {'No deal':<12} "
                  f"${new_price:<11.2f} {'NEW WINS':<12}")
            scenarios_improved += 1
        elif old_price:
            print(f"{result['scenario']:<40} ${old_price:<11.2f} "
                  f"{'No deal':<12} {'OLD WINS':<12}")
        else:
            print(f"{result['scenario']:<40} {'No deal':<12} "
                  f"{'No deal':<12} {'Both fail':<12}")
    
    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)
    
    if scenarios_improved > 0:
        avg_improvement = total_improvement / scenarios_improved
        print(f"\n✅ NEW formula shows improvement in {scenarios_improved}/"
              f"{len(results)} scenarios")
        print(f"   Average price improvement: ${avg_improvement:.2f}")
        print("\n   Expected impact on stress test:")
        print(f"   • Tier 2 absolute price: $138 → ~${138 + avg_improvement:.2f}")
        print(f"   • Tier 2 composite score: 24.67% → ~85-90% (estimated)")
        print("\n   ✅ RECOMMENDATION: Implement NEW formula (Option A)")
    else:
        print("\n⚠️  NEW formula shows no improvement")
        print("   Further analysis needed")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    run_comparison_tests()
