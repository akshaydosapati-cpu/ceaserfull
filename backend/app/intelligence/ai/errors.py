from __future__ import annotations


class AIServiceUnavailableError(RuntimeError):
    public_message = "AI service is temporarily unavailable. Please try again later."

    def __init__(
        self,
        detail: str | None = None,
        *,
        retryable: bool = True,
        provider: str | None = None,
        category: str | None = None,
    ) -> None:
        super().__init__(self.public_message)
        self.detail = detail
        self.retryable = retryable
        self.provider = provider
        self.category = category


def allows_provider_fallback(error: AIServiceUnavailableError) -> bool:
    """Return whether another eligible provider may safely handle the request."""
    return error.retryable or str(error.category or "").lower() == "model_unavailable"
