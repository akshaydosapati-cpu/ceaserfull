"""
Domain Classifier for Ceaser Predictions
Classifies content into prediction domains
"""

import re
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DomainClassifier:
    """Classify content into domains"""
    
    def __init__(self):
        # Domain keywords for classification
        self.domain_keywords = {
            "financial": [
                "expense", "budget", "income", "revenue", "profit", "loss",
                "investment", "savings", "loan", "debt", "credit", "payment",
                "tax", "financial", "money", "currency", "balance", "account",
                "transaction", "cash flow", "asset", "liability", "bank", "invoice"
            ],
            "business": [
                "sales", "market", "growth", "strategy", "company", "business",
                "revenue", "customer", "product", "service", "competitor",
                "brand", "marketing", "team", "organization", "enterprise",
                "profit", "loss", "quarterly", "annual", "forecast", "kpi"
            ],
            "career": [
                "skill", "job", "career", "promotion", "salary", "raise",
                "resume", "experience", "education", "training", "certification",
                "performance", "review", "professional", "employee", "hiring",
                "interview", "position", "role", "responsibility", "cv"
            ],
            "health": [
                "health", "fitness", "exercise", "diet", "nutrition", "weight",
                "medical", "doctor", "symptom", "treatment", "medication",
                "wellness", "mental health", "therapy", "recovery", "diagnosis",
                "blood", "cholesterol", "pressure", "heart rate", "bmi"
            ],
            "education": [
                "grade", "course", "student", "teacher", "exam", "test",
                "homework", "assignment", "project", "school", "university",
                "degree", "learning", "study", "knowledge", "skill",
                "performance", "gpa", "semester", "quarter", "lecture"
            ]
        }
    
    async def initialize(self):
        """Initialize classifier"""
        logger.info("Initializing Domain Classifier...")
        logger.info("Domain Classifier ready!")
    
    def classify(self, content: Any) -> str:
        """Classify content into a domain"""
        try:
            # Convert content to string for analysis
            if isinstance(content, dict):
                # If it's a dict (like Excel data), convert to string
                content_str = json.dumps(content, default=str).lower()
            else:
                content_str = str(content).lower()
            
            # Count keyword matches per domain
            domain_scores = {}
            for domain, keywords in self.domain_keywords.items():
                matches = sum(1 for keyword in keywords if keyword in content_str)
                domain_scores[domain] = matches
            
            # Find domain with highest score
            if domain_scores:
                max_domain = max(domain_scores, key=domain_scores.get)
                max_score = domain_scores[max_domain]
                
                # Only classify if score is significant
                if max_score >= 2:
                    logger.info(f"Classified as: {max_domain} (score: {max_score})")
                    return max_domain
            
            # Default to general
            logger.info("Classified as: general")
            return "general"
            
        except Exception as e:
            logger.error(f"Error classifying domain: {e}")
            return "general"
    
    def get_domain_info(self, domain: str) -> Dict[str, Any]:
        """Get information about a domain"""
        return {
            "domain": domain,
            "keywords_count": len(self.domain_keywords.get(domain, [])),
            "supported": domain in self.domain_keywords
        }

