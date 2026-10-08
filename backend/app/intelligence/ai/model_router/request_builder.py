from __future__ import annotations

from uuid import uuid4

from app.agents.v2.registry import AgentRegistry
from app.intelligence.ai.model_router.models import ModelRequest, RoutingPolicy, Workload, ToolDefinition


AGENT_MODEL_POLICY = {
    "bolt": ({"coding"}, {"reasoning", "tool_use"}, RoutingPolicy.QUALITY),
    "alex": ({"reasoning"}, {"long_context"}, RoutingPolicy.QUALITY),
    "friday": ({"general"}, {"fast", "tool_use"}, RoutingPolicy.FAST),
    "nova": ({"creative"}, {"fast"}, RoutingPolicy.FAST),
    "zeus": ({"reasoning"}, {"long_context"}, RoutingPolicy.QUALITY),
    "atlas": ({"general"}, {"long_context", "structured_output"}, RoutingPolicy.BALANCED),
}


def request_with_tools(
    request: ModelRequest,
    tools: list[ToolDefinition],
) -> ModelRequest:
    """Add tools to an existing ModelRequest and enable tool usage.

    Args:
        request: Existing model request
        tools: List of tool definitions to add

    Returns:
        New ModelRequest with tools enabled
    """
    return ModelRequest(
        request_id=request.request_id,
        task_type=request.task_type,
        workload=request.workload,
        required_capabilities=request.required_capabilities,
        preferred_capabilities=request.preferred_capabilities,
        preferred_model_ids=request.preferred_model_ids,
        context_size_estimate=request.context_size_estimate,
        needs_tools=True,
        tools=tools,
        needs_vision=request.needs_vision,
        needs_streaming=request.needs_streaming,
        latency_preference=request.latency_preference,
        quality_preference=request.quality_preference,
        cost_preference=request.cost_preference,
        policy=request.policy,
        agent_id=request.agent_id,
        metadata=request.metadata,
    )


def request_for_agent(
    agent_id: str, *, streaming: bool = False, context_size_estimate: int = 0,
    policy: RoutingPolicy | None = None,
    preferred_model_ids: set[str] | None = None,
) -> ModelRequest:
    if AgentRegistry().get(agent_id) is None:
        raise ValueError(f"Unknown agent: {agent_id}")
    required, preferred, default_policy = AGENT_MODEL_POLICY[agent_id]
    return ModelRequest(
        request_id=f"model_{uuid4().hex}", task_type="agent",
        workload=Workload.SOFTWARE_ENGINEERING if agent_id == "bolt" else Workload.SPECIALIST,
        required_capabilities=required,
        preferred_capabilities=preferred, needs_streaming=streaming, context_size_estimate=context_size_estimate,
        policy=policy or default_policy, agent_id=agent_id, preferred_model_ids=frozenset(preferred_model_ids or []),
    )


def request_for_agents(agent_ids: list[str], *, streaming: bool = False, context_size_estimate: int = 0, preferred_model_ids: set[str] | None = None) -> ModelRequest:
    normalized = [agent_id.lower() for agent_id in agent_ids if agent_id.lower() in AGENT_MODEL_POLICY]
    if not normalized:
        return request_for_chat(streaming=streaming, context_size_estimate=context_size_estimate)
    requests = [request_for_agent(agent_id, streaming=streaming, context_size_estimate=context_size_estimate, preferred_model_ids=preferred_model_ids) for agent_id in normalized]
    required = frozenset().union(*(item.required_capabilities for item in requests))
    preferred = frozenset().union(*(item.preferred_capabilities for item in requests))
    policy = RoutingPolicy.QUALITY if any(item.policy == RoutingPolicy.QUALITY for item in requests) else requests[0].policy
    return ModelRequest(
        request_id=f"model_{uuid4().hex}", task_type="multi_agent" if len(normalized) > 1 else "agent",
        workload=Workload.SOFTWARE_ENGINEERING if "bolt" in normalized else Workload.SPECIALIST,
        required_capabilities=required, preferred_capabilities=preferred, needs_streaming=streaming,
        context_size_estimate=context_size_estimate, policy=policy, agent_id=",".join(normalized), preferred_model_ids=frozenset(preferred_model_ids or []),
    )


def request_for_chat(*, streaming: bool = False, context_size_estimate: int = 0, task_type: str = "general", preferred_model_ids: set[str] | None = None) -> ModelRequest:
    required = {"general"}
    preferred = {"fast"}
    policy = RoutingPolicy.FAST
    if task_type in {"reasoning", "comparison", "strategy"}:
        required = {"reasoning"}
        preferred = {"long_context"}
        policy = RoutingPolicy.QUALITY
    return ModelRequest(
        request_id=f"model_{uuid4().hex}", task_type=task_type, workload=Workload.NORMAL_CHAT,
        required_capabilities=required,
        preferred_capabilities=preferred, preferred_model_ids=frozenset(preferred_model_ids or []), needs_streaming=streaming, context_size_estimate=context_size_estimate, policy=policy,
    )


def request_with_integration_tools(
    db: Any,
    user_id: str,
    request: ModelRequest,
) -> ModelRequest:
    """Add integration tools to a ModelRequest.

    Args:
        db: Database session
        user_id: User ID
        request: Existing model request

    Returns:
        ModelRequest with tools if integrations are connected
    """
    from app.services.integrations.integration_tool_service import IntegrationToolService

    tool_service = IntegrationToolService(db)
    tools = tool_service.get_available_tools(user_id)

    if not tools:
        return request

    # Convert ToolDefinition to dict format for OpenAI-compatible tools
    tool_defs = [
        ToolDefinition(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
        )
        for t in tools
    ]

    return request_with_tools(request, tool_defs)
