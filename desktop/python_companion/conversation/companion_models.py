from __future__ import annotations

import time
from collections import deque
from typing import Any, Literal

from pydantic import BaseModel, Field


ConversationMode = Literal["casual", "playful", "work", "focused", "serious", "sensitive", "urgent", "celebratory"]
SupportedLanguage = Literal["auto", "English", "Telugu", "Kannada", "Hindi", "Tamil", "Malayalam"]


class CompanionPreferences(BaseModel):
    conversation_style: Literal["balanced", "casual", "professional"] = "balanced"
    humor: Literal["off", "low", "medium", "high"] = "medium"
    roasting: Literal["off", "light", "medium"] = "light"
    preferred_address: str = ""
    proactive_mode: Literal["off", "important_only", "balanced", "companion"] = "balanced"
    social_proactivity: bool = True
    social_interruption_tolerance: float = Field(default=0.6, ge=0.0, le=1.0)
    casual_checkin_frequency: Literal["low", "balanced", "high"] = "balanced"
    language: SupportedLanguage = "auto"
    code_switching: bool = True
    technical_terms: Literal["English", "native"] = "English"


class LanguageAnalysis(BaseModel):
    primary_language: SupportedLanguage = "English"
    secondary_languages: list[SupportedLanguage] = Field(default_factory=list)
    code_switched: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PersonalityPlan(BaseModel):
    mode: ConversationMode = "casual"
    warmth: float = Field(default=0.7, ge=0.0, le=1.0)
    humor: float = Field(default=0.3, ge=0.0, le=1.0)
    sarcasm: float = Field(default=0.1, ge=0.0, le=1.0)
    formality: float = Field(default=0.2, ge=0.0, le=1.0)
    initiative: float = Field(default=0.4, ge=0.0, le=1.0)
    familiarity: float = Field(default=0.3, ge=0.0, le=1.0)
    energy: float = Field(default=0.5, ge=0.0, le=1.0)
    verbosity: Literal["short", "balanced", "detailed"] = "short"
    humor_allowed: bool = True
    roasting_allowed: bool = False


class ConversationState(BaseModel):
    conversation_id: str
    current_topic: str = ""
    conversation_mode: ConversationMode = "casual"
    detected_language: SupportedLanguage = "English"
    code_switch_languages: list[SupportedLanguage] = Field(default_factory=list)
    familiarity: float = Field(default=0.2, ge=0.0, le=1.0)
    recent_callbacks: list[str] = Field(default_factory=list, max_length=5)
    last_interaction_at: float = Field(default_factory=time.time)
    active_task: str = ""
    active_project: str = ""
    recent_social_intent: str = ""


class ProactiveDecision(BaseModel):
    should_initiate: bool
    priority: Literal["low", "normal", "important", "urgent"] = "low"
    delivery_channel: Literal["none", "activity", "notification", "overlay", "voice"] = "none"
    tone: ConversationMode = "work"
    reason: str
    structured_trigger: dict[str, Any] = Field(default_factory=dict)
