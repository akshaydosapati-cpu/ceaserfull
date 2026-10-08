__all__ = ["CeaserOrchestrator", "CompletenessValidator"]

def __getattr__(name):
    if name == "CeaserOrchestrator":
        from app.services.orchestrator.orchestrator import CeaserOrchestrator
        return CeaserOrchestrator
    if name == "CompletenessValidator":
        from app.services.orchestrator.completeness_validator import CompletenessValidator
        return CompletenessValidator
    raise AttributeError(name)
