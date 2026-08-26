from __future__ import annotations

import re

from conversation.companion_models import CompanionPreferences, LanguageAnalysis, SupportedLanguage


class LanguageAnalyzer:
    """Script-level language metadata without translated command phrase tables."""

    SCRIPTS: tuple[tuple[SupportedLanguage, range], ...] = (
        ("Hindi", range(0x0900, 0x0980)),
        ("Tamil", range(0x0B80, 0x0C00)),
        ("Telugu", range(0x0C00, 0x0C80)),
        ("Kannada", range(0x0C80, 0x0D00)),
        ("Malayalam", range(0x0D00, 0x0D80)),
    )
    LOCALES: dict[str, SupportedLanguage] = {
        "en": "English", "te": "Telugu", "kn": "Kannada",
        "hi": "Hindi", "ta": "Tamil", "ml": "Malayalam",
    }

    def analyze_provider(self, text: str, detected_language: str = "", preferences: CompanionPreferences | None = None) -> LanguageAnalysis:
        analysis = self.analyze(text, preferences)
        explicit = preferences.language if preferences and preferences.language != "auto" else None
        provider_language = self.LOCALES.get(str(detected_language or "").split("-", 1)[0].lower())
        if explicit or not provider_language:
            return analysis
        secondary = [language for language in [analysis.primary_language, *analysis.secondary_languages] if language != provider_language][:2]
        analysis.primary_language = provider_language
        analysis.secondary_languages = secondary
        analysis.code_switched = bool(secondary) and bool(preferences.code_switching if preferences else True)
        return analysis

    def analyze(self, text: str, preferences: CompanionPreferences | None = None) -> LanguageAnalysis:
        content = str(text or "")
        counts: dict[SupportedLanguage, int] = {name: 0 for name, _ in self.SCRIPTS}
        latin = len(re.findall(r"[A-Za-z]", content))
        for character in content:
            codepoint = ord(character)
            for language, script_range in self.SCRIPTS:
                if codepoint in script_range:
                    counts[language] += 1
                    break
        if latin:
            counts["English"] = latin
        ranked = sorted(((count, language) for language, count in counts.items() if count), reverse=True)
        explicit = preferences.language if preferences and preferences.language != "auto" else None
        primary: SupportedLanguage = explicit or (ranked[0][1] if ranked else "English")
        secondary = [language for _, language in ranked if language != primary][:2]
        total = sum(counts.values()) or 1
        confidence = min(1.0, (counts.get(primary, 0) or (total if explicit else 0)) / total)
        code_switched = len(ranked) > 1 and bool(preferences.code_switching if preferences else True)
        return LanguageAnalysis(
            primary_language=primary,
            secondary_languages=secondary,
            code_switched=code_switched,
            confidence=round(confidence, 3),
        )
