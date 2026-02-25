"""
Quick test to verify probe detection is working with diagnostic questions.
"""

import sys
sys.path.insert(0, '.')

from stress_scenarios.utils.information_extraction import ProbeDetector

# Initialize detector
detector = ProbeDetector()

# Test with actual diagnostic questions from market_tasks.py
test_messages = [
    "What is more important: speed or price?",
    "Why did you reject my last offer?",
    "How important is warranty length?",
    "Do you have a hard price ceiling?",
    "What is more important: speed or price? | Boulware Strategy: ...",
    "Do you have a hard price ceiling? | Boulware Strategy: ...",
]

print("=" * 70)
print("PROBE DETECTION TEST")
print("=" * 70)

for msg in test_messages:
    probe_type = detector.detect(msg)
    print(f"\nMessage: {msg[:60]}...")
    print(f"Detected: {probe_type if probe_type else 'NONE'}")
    
print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
