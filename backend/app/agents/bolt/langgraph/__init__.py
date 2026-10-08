"""LangGraph Bolt agent package.

This package provides the LangGraph-based Bolt agent implementation
for Phase 1, following the approved design in CEASER_LANGGRAPH_BOLT_PHASE1_DESIGN.md.

Architecture:
  LangGraph Bolt Agent
    ↓
  bolt_agent.py - Main agent class
    ↓
  bolt_nodes.py - Graph nodes (analyze, plan, execute, verify, repair, complete)
    ↓
  bolt_adapters.py - Tool adapters (thin wrappers around CEASER capabilities)
    ↓
  bolt_state.py - Typed state definitions
    ↓
  Existing CEASER capabilities (execution)

Usage:
  from app.agents.bolt.langgraph import create_bolt_agent

  agent = create_bolt_agent(db, user_id, project_id)
  result = agent.invoke("Build a simple Flask app")
"""
from app.agents.bolt.langgraph.bolt_agent import BoltAgent, create_bolt_agent
from app.agents.bolt.langgraph.bolt_state import BoltAgentState

__all__ = ["BoltAgent", "create_bolt_agent", "BoltAgentState"]
