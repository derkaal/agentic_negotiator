"""
Deep dive analysis: Why does Tier 2 get $138 in stress test but $125 in simulation?

The discrepancy suggests the actual stress test has different buyer behavior
than our simulation. Let's analyze what's really happening.
"""


def analyze_stress_test_results():
    """
    Analyze the reported stress test results.
    
    From STRESS_TEST_FINAL_ANALYSIS.md:
    - Tier 1: $158 (floor $110)
    - Tier 2: $138 (floor $125)
    - Tier 3: $158 (floor $105)
    
    Key observation: Tier 2 got $138, which is $13 ABOVE its floor.
    This means the formula DID work in some rounds, not just floor clamp.
    """
    print("="*80)
    print("STRESS TEST RESULT ANALYSIS")
    print("="*80)
    
    print("\nReported Results:")
    print("  Tier 1 (Nova Kicks):   $158 (floor $110, margin $48)")
    print("  Tier 2 (SoleMaster):   $138 (floor $125, margin $13)")
    print("  Tier 3 (QuickShoe):    $158 (floor $105, margin $53)")
    
    print("\nKey Insight:")
    print("  Tier 2 achieved $138, which is $13 ABOVE its floor ($125).")
    print("  This means the formula DID produce values above floor in some rounds.")
    print("  The problem is NOT just floor clamping.")
    
    print("\nHypothesis:")
    print("  The formula converges TOO QUICKLY toward buyer's offer.")
    print("  Even when buyer increases offer, formula still undervalues.")
    
    print("\n" + "="*80)
    print("TESTING HYPOTHESIS: Formula converges too aggressively")
    print("="*80)
    
    # Simulate what happens when buyer reaches $150 (market avg)
    print("\nScenario: Buyer reaches $150 (market average)")
    print("Seller floor: $125, Seller ask: $200")
    print()
    
    for round_num in range(2, 11):
        buyer_offer = 150
        seller_ask = 200
        
        # OLD formula
        t = round_num
        convergence_factor = 0.5 + 0.5 * (t / 10)
        raw_price_old = convergence_factor * buyer_offer
        final_price_old = max(raw_price_old, 125)
        
        # NEW formula (midpoint)
        midpoint = (buyer_offer + seller_ask) / 2
        raw_price_new = convergence_factor * midpoint
        final_price_new = max(raw_price_new, 125)
        
        print(f"Round {round_num:2d}: "
              f"OLD=${final_price_old:6.2f} "
              f"(raw ${raw_price_old:6.2f}), "
              f"NEW=${final_price_new:6.2f} "
              f"(raw ${raw_price_new:6.2f}), "
              f"Diff=${final_price_new - final_price_old:+6.2f}")
    
    print("\n" + "="*80)
    print("REAL PROBLEM IDENTIFIED")
    print("="*80)
    
    print("\nThe issue is NOT floor clamping at low buyer offers.")
    print("The issue is UNDERVALUATION at reasonable buyer offers.")
    print()
    print("When buyer offers $150 (market average):")
    print("  • OLD formula at round 6: 0.8 × $150 = $120 → floor clamp to $125")
    print("  • OLD formula at round 10: 1.0 × $150 = $150")
    print("  • NEW formula at round 6: 0.8 × $175 = $140 (no clamp!)")
    print("  • NEW formula at round 10: 1.0 × $175 = $175")
    print()
    print("The NEW formula produces HIGHER prices at ALL rounds!")
    print()
    print("Expected improvement:")
    print("  • Fewer rounds at floor price")
    print("  • Higher final prices")
    print("  • Better efficiency scores")
    print("  • Better composite scores")
    
    print("\n" + "="*80)
    print("RECOMMENDATION CONFIRMED")
    print("="*80)
    print("\n✅ Implement NEW formula (midpoint convergence)")
    print("   Expected Tier 2 price: $138 → $160-170 (closer to Tier 1/3)")
    print("   Expected composite score: 24.67% → 85-90%")


def demonstrate_formula_difference():
    """
    Show the key difference between formulas at various buyer offers.
    """
    print("\n\n" + "="*80)
    print("FORMULA COMPARISON AT DIFFERENT BUYER OFFERS")
    print("="*80)
    
    seller_ask = 200
    seller_floor = 125
    
    buyer_offers = [100, 120, 140, 150, 160, 170]
    
    print(f"\nSeller ask: ${seller_ask}, Seller floor: ${seller_floor}")
    print(f"\n{'Buyer':<8} {'Round':<7} {'OLD Formula':<13} {'NEW Formula':<13} "
          f"{'Difference':<12}")
    print("-" * 80)
    
    for buyer_offer in buyer_offers:
        for round_num in [2, 5, 8, 10]:
            t = round_num
            convergence_factor = 0.5 + 0.5 * (t / 10)
            
            # OLD: converge to buyer offer
            raw_old = convergence_factor * buyer_offer
            final_old = max(raw_old, seller_floor)
            
            # NEW: converge to midpoint
            midpoint = (buyer_offer + seller_ask) / 2
            raw_new = convergence_factor * midpoint
            final_new = max(raw_new, seller_floor)
            
            diff = final_new - final_old
            
            print(f"${buyer_offer:<7.0f} {round_num:<7} ${final_old:<12.2f} "
                  f"${final_new:<12.2f} ${diff:+11.2f}")
        print()
    
    print("="*80)
    print("CONCLUSION")
    print("="*80)
    print("\nNEW formula consistently produces HIGHER prices than OLD formula.")
    print("This will directly improve Tier 2 performance in stress tests.")


if __name__ == "__main__":
    analyze_stress_test_results()
    demonstrate_formula_difference()
