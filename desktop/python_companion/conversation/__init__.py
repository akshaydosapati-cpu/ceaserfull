"""Conversation and world-model foundations for CEASER Desktop."""

from conversation.companion_models import CompanionPreferences, ConversationState, LanguageAnalysis, PersonalityPlan
from conversation.companion_personality import CompanionPersonalityEngine
from conversation.proactive_conversation import ProactiveConversationEngine

__all__ = ["CompanionPersonalityEngine", "CompanionPreferences", "ConversationState", "LanguageAnalysis", "PersonalityPlan", "ProactiveConversationEngine"]
