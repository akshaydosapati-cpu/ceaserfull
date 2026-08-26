import openai
import logging
import os
import hashlib
import json
import requests
from .memory import MemoryAssistant

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AICore:
    def __init__(self, openai_api_key=None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.hf_api_key = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
        self.hf_model = os.getenv("HF_MODEL") or os.getenv("HUGGINGFACE_MODEL")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        openai.api_key = self.openai_api_key
        self.logger = logging.getLogger(__name__)
        
        # Initialize persistent memory
        self.memory = MemoryAssistant()
        
        # Simple in-memory cache for faster responses
        self.response_cache = {}

    def chat(self, prompt, context=None):
        # Clean the prompt for matching
        clean_prompt = prompt.lower().strip()
        
        # Check cache for exact match (for repeated questions)
        cache_key = hashlib.md5(clean_prompt.encode()).hexdigest()
        if cache_key in self.response_cache:
            return self.response_cache[cache_key]
        
        messages = [
            {"role": "system", "content": "You are CEASER, a professional desktop AI companion. Keep voice answers short, useful, and natural. For long work, summarize briefly and say the full result is on screen."}
        ]
        if context:
            messages.append({"role": "user", "content": f"Context: {context}"})
        messages.append({"role": "user", "content": prompt})

        for provider in (self._chat_groq, self._chat_gemini, self._chat_huggingface, self._chat_openai):
            try:
                result = provider(messages, prompt)
                if result:
                    self.response_cache[cache_key] = result
                    return result
            except Exception as exc:
                self.logger.warning("AI provider failed: %s", type(exc).__name__)
        return "AI service is temporarily unavailable. Please try again later."

    def _chat_groq(self, messages, _prompt):
        if not self.groq_api_key:
            return None
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"},
            json={"model": self.groq_model, "messages": messages, "temperature": 0.4, "max_tokens": 220},
            timeout=18,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def _chat_gemini(self, _messages, prompt):
        if not self.gemini_api_key:
            return None
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": self.gemini_api_key},
            json={"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.4, "maxOutputTokens": 220}},
            timeout=18,
        )
        response.raise_for_status()
        data = response.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "\n".join(part.get("text", "") for part in parts).strip()

    def _chat_huggingface(self, _messages, prompt):
        if not self.hf_api_key or not self.hf_model:
            return None
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{self.hf_model}",
            headers={"Authorization": f"Bearer {self.hf_api_key}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 180, "temperature": 0.4}},
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            return str(data[0].get("generated_text") or "").replace(prompt, "").strip()
        if isinstance(data, dict):
            return str(data.get("generated_text") or data.get("summary_text") or "").strip()
        return None

    def _chat_openai(self, messages, _prompt):
        if not self.openai_api_key:
            return None
        chat_api = getattr(openai, 'chat', None)
        if chat_api and hasattr(chat_api, 'completions'):
            response = openai.chat.completions.create(
                model=self.openai_model,
                messages=messages,
                max_tokens=220,
                temperature=0.4,
                timeout=18
            )
            return response.choices[0].message.content.strip()
        response = openai.ChatCompletion.create(
            model=self.openai_model,
            messages=messages,
            max_tokens=220,
            temperature=0.4,
            timeout=18
        )
        return response.choices[0].message.content.strip()

    def remember(self, key, value, category='knowledge', importance=1):
        """Store information in persistent memory"""
        try:
            success = self.memory.remember(key, value, category=category, importance=importance)
            if success:
                logger.info(f"Successfully remembered: {key} = {value}")
                return f"Remembered: {key}"
            else:
                logger.warning(f"Failed to remember: {key}")
                return f"Failed to remember: {key}"
        except Exception as e:
            logger.error(f"Error remembering {key}: {e}")
            return f"Error remembering: {e}"

    def recall(self, key, category='knowledge'):
        """Retrieve information from persistent memory"""
        try:
            value = self.memory.recall(key, category=category)
            if value is not None:
                logger.info(f"Successfully recalled: {key} = {value}")
                return value
            else:
                # Try searching for similar memories
                similar = self.memory.search_memories(key, category=category, limit=3)
                if similar:
                    logger.info(f"Found similar memories for: {key}")
                    return f"Found similar: {similar[0]['value']}"
                else:
                    logger.info(f"No memory found for: {key}")
                    return f"I don't remember anything about {key}"
        except Exception as e:
            logger.error(f"Error recalling {key}: {e}")
            return f"Error recalling: {e}" 

    def is_available(self):
        """Check if the AI core is properly configured and available"""
        return bool(self.groq_api_key or self.gemini_api_key or self.hf_api_key or self.openai_api_key)
