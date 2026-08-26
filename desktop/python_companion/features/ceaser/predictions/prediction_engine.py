"""
Ceaser Predictions Engine
Core AI prediction generation system
Adapted for Ceaser AI integration
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import openai

from .config import OPENAI_API_KEY, OPENAI_MODEL, CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

class PredictionEngine:
    """Main prediction engine for generating forecasts"""
    
    def __init__(self):
        # Use same OpenAI configuration pattern as ai_core.py
        self.openai_api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        self.model = OPENAI_MODEL
        self.confidence_threshold = CONFIDENCE_THRESHOLD
        self.stats = {
            "predictions_generated": 0,
            "domains_processed": {},
            "avg_confidence": 0.0
        }
        
        # Initialize OpenAI (same pattern as ai_core.py)
        if self.openai_api_key:
            try:
                openai.api_key = self.openai_api_key
                logger.info("OpenAI API key configured for predictions")
            except Exception as e:
                logger.warning(f"Could not set OpenAI API key: {e}")
        else:
            logger.warning("No OpenAI API key found. Predictions will use fallback mode.")
    
    async def initialize(self):
        """Initialize the prediction engine"""
        logger.info("Initializing Prediction Engine...")
        logger.info("Prediction Engine ready!")
    
    def get_stats(self):
        """Get engine statistics"""
        return self.stats
    
    def get_supported_predictions(self, domain: str) -> List[str]:
        """Get list of supported predictions for a domain"""
        domain_predictions = {
            "financial": [
                "expense_trends",
                "budget_forecast",
                "savings_projection",
                "investment_outlook",
                "cash_flow_prediction"
            ],
            "business": [
                "sales_forecast",
                "growth_projections",
                "market_trends",
                "resource_needs",
                "competition_analysis"
            ],
            "career": [
                "skill_growth",
                "promotion_timeline",
                "salary_projection",
                "career_path",
                "opportunity_detection"
            ],
            "health": [
                "health_trends",
                "risk_assessment",
                "wellness_projection",
                "fitness_goals",
                "prevention_strategy"
            ],
            "education": [
                "performance_forecast",
                "skill_development",
                "learning_path",
                "achievement_prediction",
                "study_efficiency"
            ],
            "general": [
                "trend_analysis",
                "pattern_recognition",
                "outcome_prediction",
                "recommendation_generation"
            ]
        }
        return domain_predictions.get(domain, domain_predictions["general"])
    
    async def generate_predictions(
        self,
        content: Any,
        domain: str,
        prediction_type: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate predictions based on content and domain
        """
        try:
            logger.info(f"Generating {prediction_type} predictions for {domain} domain")
            
            # Get appropriate template
            template_func = self.prediction_templates.get(domain, self._generate_general_predictions)
            
            # Generate predictions
            predictions = await template_func(content, prediction_type, context or {})
            
            # Calculate confidence
            confidence = self._calculate_confidence(predictions, domain)
            
            # Update stats
            self.stats["predictions_generated"] += 1
            if domain in self.stats["domains_processed"]:
                self.stats["domains_processed"][domain] += 1
            else:
                self.stats["domains_processed"][domain] = 1
            
            # Update average confidence
            total = self.stats["avg_confidence"] * (self.stats["predictions_generated"] - 1)
            self.stats["avg_confidence"] = (total + confidence) / self.stats["predictions_generated"]
            
            logger.info(f"Predictions generated with {confidence:.2%} confidence")
            
            return {
                "predictions": predictions,
                "confidence": confidence,
                "domain": domain,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "prediction_type": prediction_type,
                    "engine_version": "1.0.0"
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating predictions: {e}")
            return {
                "predictions": {},
                "confidence": 0.0,
                "error": str(e)
            }
    
    @property
    def prediction_templates(self):
        """Get prediction templates by domain"""
        return {
            "financial": self._generate_financial_predictions,
            "business": self._generate_business_predictions,
            "career": self._generate_career_predictions,
            "health": self._generate_health_predictions,
            "education": self._generate_education_predictions,
            "general": self._generate_general_predictions
        }
    
    def _calculate_confidence(self, predictions: Dict[str, Any], domain: str) -> float:
        """Calculate overall confidence score"""
        # Simple confidence calculation based on prediction completeness
        if not predictions:
            return 0.0
        
        num_predictions = len(predictions)
        completeness = min(num_predictions / 5, 1.0)  # Normalize to 5 predictions
        
        # Domain-specific confidence adjustments
        domain_confidence = {
            "financial": 0.85,
            "business": 0.80,
            "career": 0.75,
            "health": 0.70,
            "education": 0.75,
            "general": 0.65
        }
        
        base_confidence = domain_confidence.get(domain, 0.65)
        
        return min(base_confidence * completeness, 1.0)
    
    async def _generate_financial_predictions(
        self,
        content: Any,
        prediction_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate financial predictions"""
        prompt = f"""
        Analyze the following financial data and generate predictions:
        
        Content Summary: {str(content)[:1000]}
        
        Generate predictions for:
        1. Expense trends over the next 3 months
        2. Budget forecast accuracy
        3. Cash flow projection
        4. Savings opportunities
        5. Potential risks
        
        Format your response as JSON with specific numerical forecasts and confidence levels.
        """
        
        return await self._call_openai(prompt)
    
    async def _generate_business_predictions(
        self,
        content: Any,
        prediction_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate business predictions"""
        prompt = f"""
        Analyze the following business data and generate strategic predictions:
        
        Content Summary: {str(content)[:1000]}
        
        Generate predictions for:
        1. Sales growth trajectory
        2. Market expansion potential
        3. Resource requirements
        4. Competition positioning
        5. Strategic opportunities
        
        Format your response as JSON with actionable insights and timelines.
        """
        
        return await self._call_openai(prompt)
    
    async def _generate_career_predictions(
        self,
        content: Any,
        prediction_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate career predictions"""
        prompt = f"""
        Analyze the following career data and generate growth predictions:
        
        Content Summary: {str(content)[:1000]}
        
        Generate predictions for:
        1. Skill development trajectory
        2. Promotion potential
        3. Salary growth forecast
        4. Career opportunities
        5. Professional strengths and gaps
        
        Format your response as JSON with specific timelines and recommendations.
        """
        
        return await self._call_openai(prompt)
    
    async def _generate_health_predictions(
        self,
        content: Any,
        prediction_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate health predictions"""
        prompt = f"""
        Analyze the following health data and generate wellness predictions:
        
        Content Summary: {str(content)[:1000]}
        
        Generate predictions for:
        1. Health trend projections
        2. Risk assessment
        3. Fitness goal achievement
        4. Prevention opportunities
        5. Wellness recommendations
        
        Format your response as JSON with personalized insights and action plans.
        """
        
        return await self._call_openai(prompt)
    
    async def _generate_education_predictions(
        self,
        content: Any,
        prediction_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate education predictions"""
        prompt = f"""
        Analyze the following education data and generate learning predictions:
        
        Content Summary: {str(content)[:1000]}
        
        Generate predictions for:
        1. Performance forecast
        2. Skill mastery timeline
        3. Learning efficiency
        4. Knowledge retention
        5. Achievement potential
        
        Format your response as JSON with specific milestones and study recommendations.
        """
        
        return await self._call_openai(prompt)
    
    async def _generate_general_predictions(
        self,
        content: Any,
        prediction_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate general predictions"""
        prompt = f"""
        Analyze the following content and generate intelligent predictions:
        
        Content Summary: {str(content)[:1000]}
        
        Generate predictions for:
        1. Trend identification
        2. Pattern recognition
        3. Outcome forecasting
        4. Action recommendations
        5. Key insights
        
        Format your response as JSON with clear predictions and confidence levels.
        """
        
        return await self._call_openai(prompt)
    
    async def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI API for predictions (same pattern as ai_core.py)"""
        try:
            if not self.openai_api_key:
                logger.warning("OpenAI API key not configured")
                return self._generate_fallback_predictions()
            
            messages = [
                {"role": "system", "content": "You are an expert prediction analyst. Generate accurate, actionable predictions in JSON format with specific forecasts, timelines, and confidence levels."},
                {"role": "user", "content": prompt}
            ]
            
            # Try new API format first (same as ai_core.py)
            try:
                chat_api = getattr(openai, 'chat', None)
                if chat_api and hasattr(chat_api, 'completions'):
                    response = openai.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=1000,
                        temperature=0.7,
                        timeout=30  # 30 second timeout for predictions
                    )
                    
                    if response and hasattr(response, 'choices') and response.choices and len(response.choices) > 0:
                        content = response.choices[0].message.content
                        
                        # Try to parse JSON response
                        try:
                            parsed = json.loads(content)
                            return parsed if isinstance(parsed, dict) else {"insights": content}
                        except json.JSONDecodeError:
                            # If not JSON, wrap in structure
                            return {
                                "insights": content,
                                "formatted": False
                            }
            except Exception as e:
                logger.debug(f"New API format failed, trying fallback: {e}")
            
            # Fallback to old interface (same as ai_core.py)
            try:
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=1000,
                    temperature=0.7,
                    timeout=30
                )
                
                if response and response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    
                    # Try to parse JSON response
                    try:
                        parsed = json.loads(content)
                        return parsed if isinstance(parsed, dict) else {"insights": content}
                    except json.JSONDecodeError:
                        return {
                            "insights": content,
                            "formatted": False
                        }
            except Exception as e:
                logger.error(f"Error with OpenAI API fallback: {e}")
            
            return self._generate_fallback_predictions()
            
        except Exception as e:
            logger.error(f"Error calling OpenAI: {e}")
            return self._generate_fallback_predictions()
    
    def _generate_fallback_predictions(self) -> Dict[str, Any]:
        """Generate fallback predictions when AI is unavailable"""
        return {
            "status": "fallback",
            "message": "Using rule-based predictions",
            "predictions": {
                "trend": "Stable trajectory expected",
                "recommendation": "Monitor progress regularly",
                "confidence": 0.6
            }
        }

