"""Secondary synthesis — three sub-agents, each using an agentic web-search loop.

Architecture:
- `web_search` tool backed by `duckduckgo-search`. Returns title/url/snippet.
- `submit_*` tools: one per sub-agent. Their `input_schema` is the JSON schema
  of the sub-agent's output Pydantic model. When Claude calls the submit tool,
  the agentic loop exits and we parse its arguments.
- `run_agent_loop` drives the loop — interleaves tool calls, records each search
  into `state.history`, and returns the parsed submission.

All three sub-agents use Opus 4.7. The DDG search tool has a small retry + rate
limiting built in so a transient DDG throttle doesn't kill a 30s run.

Results land at:
- state.secondary["cultural_risk"]
- state.secondary["competitive_analysis"]
- state.secondary["market_context"]
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Optional

from prism import state as S
from prism.client import get_client
from prism.schemas import (
    CompetitiveAnalysisSynthesis,
    CulturalRiskSynthesis,
    MarketContextSynthesis,
)


MAX_LOOP_ITERATIONS = 20  # hard ceiling; sub-agents typically need 4-10 searches
MAX_SEARCH_RESULTS = 6


# ---------------------------------------------------------------------------
# DuckDuckGo search tool
# ---------------------------------------------------------------------------


def _ddg_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Run a DuckDuckGo search. Returns [{title, url, snippet}, ...].

    Small retry + 500ms stagger for transient throttling.
    """
    from ddgs import DDGS

    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href") or r.get("url") or "",
                    "snippet": r.get("body") or r.get("snippet") or "",
                }
                for r in raw
            ]
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.5 * (attempt + 1))

    raise RuntimeError(f"DuckDuckGo search failed after 3 attempts: {last_err}")


WEB_SEARCH_TOOL: dict = {
    "name": "web_search",
    "description": (
        "Search the open web via DuckDuckGo. Use this for any factual claim "
        "you'll cite — markets, competitors, cultural conventions, design norms, "
        "trend signals. Keep queries concise (3-8 words). Returns a list of "
        "{title, url, snippet}."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query.",
            }
        },
        "required": ["query"],
    },
}


# ---------------------------------------------------------------------------
# Pydantic -> tool input_schema
# ---------------------------------------------------------------------------


def _pydantic_tool_schema(model_cls) -> dict:
    """Pydantic v2 `model_json_schema` returns a proper JSON Schema with $defs.
    Anthropic's tool API accepts this shape directly.
    """
    schema = model_cls.model_json_schema()
    # Make sure top level is an object; Pydantic always produces that for BaseModel.
    if schema.get("type") != "object":
        schema["type"] = "object"
    return schema


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_cultural_risk(state: S.State) -> Optional[CulturalRiskSynthesis]:
    if not state.secondary:
        return None
    data = state.secondary.get("cultural_risk")
    return CulturalRiskSynthesis.model_validate(data) if data else None


def get_competitive(state: S.State) -> Optional[CompetitiveAnalysisSynthesis]:
    if not state.secondary:
        return None
    data = state.secondary.get("competitive_analysis")
    return CompetitiveAnalysisSynthesis.model_validate(data) if data else None


def get_market_context(state: S.State) -> Optional[MarketContextSynthesis]:
    if not state.secondary:
        return None
    data = state.secondary.get("market_context")
    return MarketContextSynthesis.model_validate(data) if data else None


def _set_secondary(state: S.State, key: str, value) -> None:
    if state.secondary is None:
        state.secondary = {}
    state.secondary[key] = value.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------


def _run_agent_loop(
    *,
    state: S.State,
    sub_agent_key: str,
    system: str,
    user_prompt: str,
    submit_tool_name: str,
    submit_model_cls,
    model: str = "claude-haiku-4-5",
    on_search: Optional[Callable[[str, int], None]] = None,
) -> dict:
    """Run the web-search + submit-tool agentic loop.

    Returns the raw dict arguments from the submit tool call (caller parses
    with Pydantic). Each web_search call is recorded to state.history so the
    PM has a complete audit trail.
    """
    client = get_client()

    submit_tool = {
        "name": submit_tool_name,
        "description": (
            f"Submit the final {submit_model_cls.__name__}. Call this EXACTLY once "
            "when you have gathered enough evidence. After this call you will exit."
        ),
        "input_schema": _pydantic_tool_schema(submit_model_cls),
    }
    tools = [WEB_SEARCH_TOOL, submit_tool]

    messages: list[dict] = [{"role": "user", "content": user_prompt}]

    for iteration in range(MAX_LOOP_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=8000,
            system=system,
            messages=messages,
            tools=tools,
        )

        # Append assistant turn (as-is — the SDK accepts ContentBlock objects)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason not in ("tool_use", "end_turn"):
            raise RuntimeError(
                f"Unexpected stop_reason from agent: {response.stop_reason}"
            )

        tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        if not tool_use_blocks:
            if response.stop_reason == "end_turn":
                raise RuntimeError(
                    f"Agent `{sub_agent_key}` ended without calling `{submit_tool_name}`. "
                    "Tighten the system prompt so the model always submits."
                )
            # Weird case: tool_use stop reason but no tool blocks
            continue

        # Process all tool uses. If any is the submit tool, capture and exit.
        tool_results: list[dict] = []
        submit_payload: Optional[dict] = None

        for block in tool_use_blocks:
            if block.name == submit_tool_name:
                submit_payload = dict(block.input)
                continue

            if block.name == WEB_SEARCH_TOOL["name"]:
                query = block.input.get("query", "").strip()
                try:
                    results = _ddg_search(query)
                except Exception as e:  # noqa: BLE001
                    results = {"error": str(e)}

                if on_search:
                    on_search(query, len(results) if isinstance(results, list) else 0)

                S.append_history(
                    state,
                    actor=sub_agent_key,
                    action="web_search",
                    details={
                        "query": query,
                        "result_count": len(results) if isinstance(results, list) else 0,
                        "urls": [r.get("url", "") for r in results]
                        if isinstance(results, list)
                        else [],
                    },
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(results, ensure_ascii=False),
                    }
                )
                continue

            # Unknown tool — return an error result so the model can recover
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": f"Unknown tool: {block.name}",
                }
            )

        if submit_payload is not None:
            return submit_payload

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(
        f"Agent `{sub_agent_key}` exceeded max_iterations={MAX_LOOP_ITERATIONS} "
        f"without calling `{submit_tool_name}`."
    )


# ---------------------------------------------------------------------------
# Common setup-context builder
# ---------------------------------------------------------------------------


def _setup_context(state: S.State) -> str:
    assert state.setup is not None
    setup = state.setup
    pc = setup.product_context
    markets = ", ".join(f"{m.country} ({m.locale})" for m in setup.target_markets)
    variants = "\n".join(
        f"- `{v.id}`: {v.label}" + (" (CONTROL)" if v.is_control else "")
        for v in setup.variants
    )
    return (
        f"Asset: {pc.application} · {pc.asset_type} · feature: {pc.feature}\n"
        f"Use case: {pc.use_case}\n"
        f"Source: {setup.source_market.country} ({setup.source_market.locale})\n"
        f"Targets: {markets}\n"
        f"Hypothesis: {setup.hypothesis}\n"
        f"Variants:\n{variants}"
    )


# ---------------------------------------------------------------------------
# Sub-agent 1: Cultural Risk
# ---------------------------------------------------------------------------


_CULTURAL_RISK_SYSTEM = (
    "Surface cultural sensitivities, taboos, and misalignment risks in the target "
    "market(s). Rules:\n"
    "- Use web_search; every material claim needs a web_source citation with a real URL.\n"
    "- Cite named articles/orgs/guidelines; no vague 'sources say'.\n"
    "- severity_0_100: 80+ blocks ship, 50-79 needs mitigation, <50 worth noting. "
    "Full range; don't cluster.\n"
    "- Call submit_cultural_risk exactly once when done."
)


def run_cultural_risk(
    state: S.State,
    on_search: Optional[Callable[[str, int], None]] = None,
) -> CulturalRiskSynthesis:
    if state.setup is None:
        raise RuntimeError("state.setup is required before secondary synthesis.")

    markets = [m.locale for m in state.setup.target_markets]
    user = (
        _setup_context(state)
        + f"\n\nResearch cultural risks for {', '.join(markets)}. Focus: religious/"
        f"political/social taboos, gender/representation norms, seasonal timing, "
        f"name + imagery conventions. Use web_search for current sources. "
        f"Then submit_cultural_risk."
    )

    payload = _run_agent_loop(
        state=state,
        sub_agent_key="cultural_risk_agent",
        system=_CULTURAL_RISK_SYSTEM,
        user_prompt=user,
        submit_tool_name="submit_cultural_risk",
        submit_model_cls=CulturalRiskSynthesis,
        on_search=on_search,
    )
    result = CulturalRiskSynthesis.model_validate(payload)
    _set_secondary(state, "cultural_risk", result)
    S.append_history(
        state,
        actor="cultural_risk_agent",
        action="synthesis_submitted",
        details={
            "findings_count": len(result.findings),
            "overall_risk": result.overall_risk_0_100,
        },
    )
    S.save(state)
    return result


# ---------------------------------------------------------------------------
# Sub-agent 2: Competitive Analysis
# ---------------------------------------------------------------------------


_COMPETITIVE_SYSTEM = (
    "Profile competitors serving the same asset-creation need in the target market(s). Rules:\n"
    "- Use web_search; every competitor/capability claim needs a real URL.\n"
    "- Focus on market-relevant competitors, not a generic design-tools list.\n"
    "- threat_level_0_100: 80+ dominant incumbent, 50-79 meaningful share, <50 peripheral.\n"
    "- Concrete threats + opportunities. Call submit_competitive_analysis once when done."
)


def run_competitive_analysis(
    state: S.State,
    on_search: Optional[Callable[[str, int], None]] = None,
) -> CompetitiveAnalysisSynthesis:
    if state.setup is None:
        raise RuntimeError("state.setup is required before secondary synthesis.")

    markets = [f"{m.country} ({m.locale})" for m in state.setup.target_markets]
    user = (
        _setup_context(state)
        + f"\n\nProfile competitors for {state.setup.product_context.application}'s "
        f"{state.setup.product_context.asset_type} in {', '.join(markets)}. "
        f"Prioritize local-market competitors (not only US ones). "
        f"Then submit_competitive_analysis."
    )

    payload = _run_agent_loop(
        state=state,
        sub_agent_key="competitive_agent",
        system=_COMPETITIVE_SYSTEM,
        user_prompt=user,
        submit_tool_name="submit_competitive_analysis",
        submit_model_cls=CompetitiveAnalysisSynthesis,
        on_search=on_search,
    )
    result = CompetitiveAnalysisSynthesis.model_validate(payload)
    _set_secondary(state, "competitive_analysis", result)
    S.append_history(
        state,
        actor="competitive_agent",
        action="synthesis_submitted",
        details={"competitors_count": len(result.competitors)},
    )
    S.save(state)
    return result


# ---------------------------------------------------------------------------
# Sub-agent 3: Market Context
# ---------------------------------------------------------------------------


_MARKET_CONTEXT_SYSTEM = (
    "Surface sizing, growth signals, audience behavior, adjacent trends. Rules:\n"
    "- Use web_search; every quantitative/trend claim needs a real URL.\n"
    "- Qualitative sizing is fine when data is scarce — say so explicitly.\n"
    "- Behaviors = what the audience does today (tools/channels/workflows), not personas.\n"
    "- Call submit_market_context once when done."
)


def run_market_context(
    state: S.State,
    on_search: Optional[Callable[[str, int], None]] = None,
) -> MarketContextSynthesis:
    if state.setup is None:
        raise RuntimeError("state.setup is required before secondary synthesis.")

    markets = [f"{m.country} ({m.locale})" for m in state.setup.target_markets]
    user = (
        _setup_context(state)
        + f"\n\nResearch market context for {', '.join(markets)}. Cover sizing, "
        f"growth signals, audience behaviors, adjacent trends. Then submit_market_context."
    )

    payload = _run_agent_loop(
        state=state,
        sub_agent_key="market_context_agent",
        system=_MARKET_CONTEXT_SYSTEM,
        user_prompt=user,
        submit_tool_name="submit_market_context",
        submit_model_cls=MarketContextSynthesis,
        on_search=on_search,
    )
    result = MarketContextSynthesis.model_validate(payload)
    _set_secondary(state, "market_context", result)
    S.append_history(
        state,
        actor="market_context_agent",
        action="synthesis_submitted",
        details={
            "growth_signals_count": len(result.growth_signals),
            "citations_count": len(result.citations),
        },
    )
    S.save(state)
    return result
