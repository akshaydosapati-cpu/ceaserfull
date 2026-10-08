"""Adapter to provide CEASER's ModelRouter as a LangChain-compatible LLM."""
from __future__ import annotations

from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs import LLMResult, Generation


class CeaserModelAdapter(BaseChatModel):
    """Wraps CEASER's ModelRouter as a LangChain-compatible language model.

    This adapter exposes CEASER's existing model routing logic (which handles
    provider selection, fallbacks, health tracking, and configuration) as a
    LangChain-compatible LLM for use in LangGraph agents.
    """

    model_config = {"arbitrary_types_allowed": True}
    model_router: Any = None

    def __init__(self, model_router: Any):
        """Initialize adapter with a ModelRouter instance.

        Args:
            model_router: CEASER ModelRouter instance from app.intelligence.ai.model_router

        Raises:
            ValueError: If model_router is None
        """
        super().__init__(model_router=model_router)
        if not model_router:
            raise ValueError("model_router is required")

    @property
    def _llm_type(self) -> str:
        """Return LLM type identifier."""
        return "ceaser_model_router"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Generate response using CEASER's ModelRouter.

        Calls the existing router.generate() which handles:
        - Model selection based on request type and workload
        - Provider fallback on failure
        - Health tracking and cooldown management
        - Configuration and capability matching

        Args:
            messages: List of LangChain BaseMessage objects
            stop: Optional stop sequences
            run_manager: Optional callback manager
            **kwargs: Additional arguments

        Returns:
            LLMResult with generations

        Raises:
            RuntimeError: If ModelRouter not initialized
        """
        if not self.model_router:
            raise RuntimeError("ModelRouter not initialized")

        # Convert LangChain messages to plain text prompt
        prompt_text = "\n".join([f"{msg.type}: {msg.content}" for msg in messages])

        # Call router.generate() via async wrapper
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, use run_coroutine_threadsafe
            future = asyncio.ensure_future(
                self.model_router.generate(
                    request={"type": "chat"},
                    instructions="You are a helpful research assistant.",
                    input_text=prompt_text,
                    max_output_tokens=None,
                )
            )
            response = loop.run_until_complete(future)
        except RuntimeError:
            # No running loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(
                    self.model_router.generate(
                        request={"type": "chat"},
                        instructions="You are a helpful research assistant.",
                        input_text=prompt_text,
                        max_output_tokens=None,
                    )
                )
            finally:
                loop.close()

        response_text = response.content if hasattr(response, "content") else str(response)
        generation = Generation(text=response_text)
        return LLMResult(generations=[[generation]])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Async generate using CEASER's ModelRouter.

        Args:
            messages: List of LangChain BaseMessage objects
            stop: Optional stop sequences
            run_manager: Optional callback manager
            **kwargs: Additional arguments

        Returns:
            LLMResult with generations

        Raises:
            RuntimeError: If ModelRouter not initialized
        """
        if not self.model_router:
            raise RuntimeError("ModelRouter not initialized")

        prompt_text = "\n".join([f"{msg.type}: {msg.content}" for msg in messages])

        response = await self.model_router.generate(
            request={"type": "chat"},
            instructions="You are a helpful research assistant.",
            input_text=prompt_text,
            max_output_tokens=None,
        )
        response_text = response.content if hasattr(response, "content") else str(response)

        generation = Generation(text=response_text)
        return LLMResult(generations=[[generation]])
