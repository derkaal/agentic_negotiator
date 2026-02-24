"""
Information Extraction Module

Detects probing questions from sellers and simulates buyer responses
based on hidden information asymmetries.
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Discovery:
    """Represents a discovered piece of hidden information"""
    asymmetry_type: str
    discovered_at_round: int
    probe_message: str
    buyer_response: str
    revealed_value: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ProbeDetector:
    """
    Detects probing questions in seller messages using keyword patterns
    """
    
    # Keyword patterns for different probe types
    PROBE_PATTERNS = {
        "urgency": [
            r"\btimeline\b",
            r"\bdeadline\b",
            r"\bwhen.*need\b",
            r"\bhow soon\b",
            r"\btime.*frame\b",
            r"\btime.*sensitive\b",
            r"\burgent\b",
            r"\bquickly\b",
            r"\brushing\b"
        ],
        "budget": [
            r"\bbudget\b",
            r"\bmaximum\b",
            r"\bmax.*price\b",
            r"\bhow much.*afford\b",
            r"\bspend\b",
            r"\bprice.*range\b",
            r"\bflexib.*budget\b",
            r"\btop.*dollar\b"
        ],
        "alternatives": [
            r"\bother.*offers?\b",
            r"\bcompet.*offers?\b",
            r"\balternatives?\b",
            r"\bother.*options?\b",
            r"\bcomparing\b",
            r"\bother.*sellers?\b",
            r"\bbest.*offers?\b",
            r"\bproof\b"
        ],
        "quality": [
            r"\bpriority\b",
            r"\bimportant.*feature\b",
            r"\bquality\b",
            r"\bprefer\b",
            r"\bvalue.*most\b",
            r"\bcare.*about\b",
            r"\bmatter.*most\b",
            r"\bfeature.*need\b"
        ]
    }
    
    def __init__(self):
        # Compile patterns for efficiency
        self.compiled_patterns = {
            probe_type: [
                re.compile(pattern, re.IGNORECASE)
                for pattern in patterns
            ]
            for probe_type, patterns in self.PROBE_PATTERNS.items()
        }
    
    def detect(self, message: str) -> Optional[str]:
        """
        Detect probe type from seller message
        
        Args:
            message: Seller's message text
            
        Returns:
            Probe type if detected, None otherwise
        """
        if not message:
            return None
        
        # Check each probe type
        for probe_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(message):
                    return probe_type
        
        return None
    
    def detect_all(self, message: str) -> List[str]:
        """
        Detect all probe types in message
        
        Args:
            message: Seller's message text
            
        Returns:
            List of detected probe types
        """
        detected = []
        
        for probe_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(message):
                    detected.append(probe_type)
                    break  # Only add each type once
        
        return detected


class BuyerResponseGenerator:
    """
    Generates buyer responses to probing questions based on asymmetries
    """
    
    # Response templates for when buyer reveals information
    REVEAL_TEMPLATES = {
        "urgency": [
            "Actually, I need this by round {deadline}.",
            "To be honest, I'm on a tight timeline - round {deadline}.",
            "I should mention I have a deadline at round {deadline}."
        ],
        "budget": [
            "My actual maximum is ${actual_max}.",
            "I can go up to ${actual_max} if needed.",
            "Between us, my real budget is ${actual_max}."
        ],
        "alternatives": [
            "The other offer is actually ${actual_alternative}.",
            "To be honest, my alternative is ${actual_alternative}.",
            "The competing offer is ${actual_alternative}."
        ],
        "quality": [
            "Quality is actually more important to me than price.",
            "I really value {actual_preference} over everything.",
            "To be honest, {actual_preference} matters most to me."
        ]
    }
    
    # Response templates for when buyer hides information
    HIDE_TEMPLATES = {
        "urgency": [
            "No particular rush.",
            "I'm flexible on timing.",
            "Whenever works for you."
        ],
        "budget": [
            "I'd prefer to stick to my stated budget.",
            "That's really my maximum.",
            "I can't go higher than I mentioned."
        ],
        "alternatives": [
            "I have other options I'm considering.",
            "There are competitive offers out there.",
            "I'm exploring multiple sellers."
        ],
        "quality": [
            "Price is my main concern.",
            "I'm looking for the best deal.",
            "Cost is the priority for me."
        ]
    }
    
    def generate_response(
        self,
        probe_type: str,
        asymmetry: Any,
        should_reveal: bool
    ) -> str:
        """
        Generate buyer response to probe
        
        Args:
            probe_type: Type of probe detected
            asymmetry: AsymmetryType instance
            should_reveal: Whether buyer reveals information
            
        Returns:
            Generated response text
        """
        import random
        
        if should_reveal:
            templates = self.REVEAL_TEMPLATES.get(probe_type, [])
            if not templates:
                return "Let me think about that..."
            
            template = random.choice(templates)
            hidden_value = asymmetry.get_hidden_value()
            
            # Format template with hidden values
            try:
                return template.format(**hidden_value)
            except (KeyError, AttributeError):
                return template
        else:
            templates = self.HIDE_TEMPLATES.get(probe_type, [])
            if not templates:
                return "I'd prefer not to discuss that."
            
            return random.choice(templates)


class InformationExtractor:
    """
    Tracks information extraction attempts and discoveries
    """
    
    def __init__(self):
        self.probe_detector = ProbeDetector()
        self.response_generator = BuyerResponseGenerator()
        self.discoveries: List[Discovery] = []
        self.probe_attempts: Dict[str, int] = {
            "urgency": 0,
            "budget": 0,
            "alternatives": 0,
            "quality": 0
        }
    
    def process_message(
        self,
        seller_message: str,
        buyer_asymmetries: Dict[str, Any],
        current_round: int
    ) -> Optional[Discovery]:
        """
        Process seller message and detect information extraction
        
        Args:
            seller_message: Message from seller
            buyer_asymmetries: Dict of asymmetry type -> AsymmetryType
            current_round: Current negotiation round
            
        Returns:
            Discovery if information was extracted, None otherwise
        """
        # Detect probe type
        probe_type = self.probe_detector.detect(seller_message)
        
        if not probe_type:
            return None
        
        # Track probe attempt
        self.probe_attempts[probe_type] = (
            self.probe_attempts.get(probe_type, 0) + 1
        )
        
        # Check if buyer has this asymmetry
        asymmetry = buyer_asymmetries.get(probe_type)
        if not asymmetry:
            return None
        
        # Check if already revealed
        if asymmetry.revealed:
            return None
        
        # Determine if buyer reveals
        should_reveal = asymmetry.should_reveal_if_asked()
        
        # Generate buyer response
        buyer_response = self.response_generator.generate_response(
            probe_type,
            asymmetry,
            should_reveal
        )
        
        # If revealed, create discovery
        if should_reveal:
            asymmetry.mark_revealed(current_round)
            
            discovery = Discovery(
                asymmetry_type=probe_type,
                discovered_at_round=current_round,
                probe_message=seller_message,
                buyer_response=buyer_response,
                revealed_value=asymmetry.get_hidden_value()
            )
            
            self.discoveries.append(discovery)
            return discovery
        
        return None
    
    def get_extraction_rate(self) -> float:
        """
        Calculate information extraction rate
        
        Returns:
            Percentage of asymmetries discovered (0.0 to 1.0)
        """
        total_probes = sum(self.probe_attempts.values())
        if total_probes == 0:
            return 0.0
        
        return len(self.discoveries) / total_probes
    
    def get_discoveries_by_type(
        self,
        asymmetry_type: str
    ) -> List[Discovery]:
        """Get all discoveries of a specific type"""
        return [
            d for d in self.discoveries
            if d.asymmetry_type == asymmetry_type
        ]
    
    def get_discovery_summary(self) -> Dict[str, Any]:
        """
        Get summary of extraction performance
        
        Returns:
            Dict with extraction metrics
        """
        return {
            "total_probes": sum(self.probe_attempts.values()),
            "total_discoveries": len(self.discoveries),
            "extraction_rate": self.get_extraction_rate(),
            "probes_by_type": self.probe_attempts.copy(),
            "discoveries_by_type": {
                asymmetry_type: len(self.get_discoveries_by_type(
                    asymmetry_type
                ))
                for asymmetry_type in self.probe_attempts.keys()
            }
        }
