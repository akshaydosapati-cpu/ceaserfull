"""
Configuration for Prediction Engine
Uses existing Ceaser AI configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Use existing OpenAI configuration from ai_core
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))

