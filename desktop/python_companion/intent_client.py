import requests
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class IntentClient:
    """
    Thin client to communicate with the Central Backend for intent analysis and execution.
    """
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url.rstrip("/")
        self.session = requests.Session()

    def analyze_intent(self, text: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Send text to backend for intent analysis.
        """
        try:
            payload = {
                "text": text,
                "context": context or {}
            }
            response = self.session.post(f"{self.backend_url}/intent/analyze", json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to backend.")
            return {"intent": "ERROR", "error": "Backend Unavailable"}
        except Exception as e:
            logger.error(f"Error analyzing intent: {e}")
            return {"intent": "ERROR", "error": str(e)}

    def execute_action(self, action_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Request backend to execute a specific action.
        """
        try:
            response = self.session.post(f"{self.backend_url}/execution/{action_type}", json=parameters, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return {"status": "error", "message": str(e)}

    def check_health(self) -> bool:
        """
        Check if backend is reachable.
        """
        try:
            response = self.session.get(f"{self.backend_url}/health", timeout=2) # Assuming a health endpoint exists or we use root
            return response.status_code == 200
        except:
            return False
