"""
Test script to run market simulation and verify results.
"""
import asyncio
import json
from market_tasks import run_market_3x3

async def test_market():
    print("=" * 80)
    print("TESTING MARKET SIMULATION")
    print("=" * 80)
    
    events = []
    async for event in run_market_3x3(scenario="sneaker", max_rounds=10):
        events.append(event)
        event_type = event.get("type", event.get("event", "unknown"))
        print(f"\n[{event_type.upper()}]")
        
        if event_type == "round_0_discovery":
            print(f"  Discovered Avg: ${event['discovered_avg']:.2f}")
            print(f"  Baseline Avg: ${event['baseline_avg']:.2f}")
            print(f"  Seller Asks: {event['seller_asks']}")
            print(f"  Log: {event['discovery_log']}")
        
        elif event_type == "market_start":
            print(f"  Scenario: {event['scenario']}")
            print(f"  Market Avg: ${event['market_avg']:.2f}")
            print(f"  Buyers: {len(event['buyers'])}")
            print(f"  Sellers: {len(event['sellers'])}")
            for seller in event['sellers']:
                print(f"    - {seller['name']} (Tier {seller.get('tier', 'N/A')}): floor=${seller['floor']:.2f}, ask=${seller['ask']:.2f}")
        
        elif event_type == "market_round":
            print(f"  Round: {event['round']}")
            print(f"  Pairs: {len(event['pairs'])}")
        
        elif event_type == "deal_closed":
            print(f"  {event['buyer_name']} ↔ {event['seller_name']}")
            print(f"  Price: ${event['deal_price']:.2f} (Round {event['round']})")
            print(f"  Buyer Score: {event['buyer_score_adj']:.2f}")
            print(f"  Seller Score: {event['seller_score_adj']:.2f}")
            print(f"  Global Score: {event['global_score']:.2f}")
            print(f"  Pareto Optimal: {event['pareto_optimal']}")
            print(f"  Hallucinations: {event['hallucination_count']}")
        
        elif event_type == "market_end":
            print(f"\n{'=' * 80}")
            print("MARKET END - AUDIT TRAIL")
            print(f"{'=' * 80}")
            print(f"  Deals Closed: {event['closed']}/{event['possible']}")
            print(f"  Deal Rate: {event['deal_rate']:.1%}")
            print(f"  Avg Global Score: {event.get('global_score', 'N/A')}")
            print(f"  Avg Price: ${event.get('avg_deal_price', 0):.2f}")
            print(f"  Avg Rounds: {event.get('avg_rounds_to_deal', 0):.1f}")
            
            print(f"\n  SELLER RANKINGS BY TOTAL SURPLUS:")
            for rank_info in event['superiority_verdict']['by_surplus']['ranking']:
                print(f"    {rank_info['rank']}. {rank_info['seller']} (Tier {rank_info['tier']}): ${rank_info['surplus']:.2f}")
            
            print(f"\n  SELLER RANKINGS BY GLOBAL SCORE:")
            for rank_info in event['superiority_verdict']['by_global_score']['ranking']:
                print(f"    {rank_info['rank']}. {rank_info['seller']} (Tier {rank_info['tier']}): {rank_info['score']:.2f}")
            
            print(f"\n  SELLER RANKINGS BY EFFICIENCY (Rounds to Close):")
            for rank_info in event['superiority_verdict']['by_efficiency']['ranking']:
                print(f"    {rank_info['rank']}. {rank_info['seller']} (Tier {rank_info['tier']}): {rank_info['deals']} deals, {rank_info['avg_rounds']:.1f} avg rounds")
            
            print(f"\n  HALLUCINATION SUMMARY:")
            hall_summary = event['superiority_verdict']['hallucination_summary']
            print(f"    Total Floor Violations: {hall_summary['total_floor_violations']}")
            print(f"    Violating Sellers: {', '.join(hall_summary['violating_sellers']) if hall_summary['violating_sellers'] else 'None'}")
            if hall_summary['critical_events']:
                print(f"    Critical Events:")
                for h_event in hall_summary['critical_events']:
                    print(f"      - {h_event['seller']} (Round {h_event['round']}): Offered ${h_event['offered_price']:.2f} below floor ${h_event['floor_price']:.2f}")
            
            print(f"\n  AUDIT TRAIL:")
            for deal in event['audit_trail']:
                print(f"    {deal['buyer']} ↔ {deal['seller']} (Tier {deal['seller_tier']})")
                print(f"      Price: ${deal['deal_price']:.2f}, Round: {deal['round']}")
                print(f"      Buyer Surplus: ${deal['buyer_surplus']:.2f}, Seller Surplus: ${deal['seller_surplus']:.2f}")
                print(f"      Scores: Buyer={deal['buyer_score']:.2f}, Seller={deal['seller_score']:.2f}, Global={deal['global_score']:.2f}")
                print(f"      Pareto: {deal['pareto_optimal']}, Hallucinations: {deal['hallucination_count']}")
    
    print(f"\n{'=' * 80}")
    print("TEST COMPLETE")
    print(f"{'=' * 80}")
    print(f"Total events: {len(events)}")
    
    # Verify expected outcomes
    print(f"\n{'=' * 80}")
    print("VERIFICATION")
    print(f"{'=' * 80}")
    
    market_end = next((e for e in events if e.get("type") == "market_end" or e.get("event") == "market_end"), None)
    if market_end:
        print("✓ Market end event found")
        print(f"✓ Seller comparison data: {len(market_end.get('seller_comparison', {}))} sellers")
        print(f"✓ Superiority verdict: {len(market_end.get('superiority_verdict', {}))} categories")
        print(f"✓ Audit trail: {len(market_end.get('audit_trail', []))} deals")
        
        # Check for required fields
        verdict = market_end.get('superiority_verdict', {})
        if 'by_surplus' in verdict:
            print("✓ Rankings by Total Surplus Captured present")
        if 'by_global_score' in verdict:
            print("✓ Rankings by GlobalScore present")
        if 'by_efficiency' in verdict:
            print("✓ Rankings by Efficiency (Rounds to Close) present")
        if 'hallucination_summary' in verdict:
            print("✓ Hallucination flagging present")
    else:
        print("✗ Market end event not found")
    
    round_0 = next((e for e in events if e.get("type") == "round_0_discovery" or e.get("event") == "round_0_discovery"), None)
    if round_0:
        print("✓ Round 0 Discovery phase executed")
        print(f"  Discovered avg: ${round_0['discovered_avg']:.2f}")
    else:
        print("✗ Round 0 Discovery not found")

if __name__ == "__main__":
    asyncio.run(test_market())
