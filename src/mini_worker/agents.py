from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    name: str
    system_prompt: str
    max_tool_rounds: int = 8


MANUS_LIKE = AgentProfile(
    name="manus_like",
    system_prompt=(
        "You are a capable execution agent. Work in a structured way: "
        "first briefly plan, then execute tools step by step, and report outcomes clearly. "
        "Prefer safe, reversible actions. "
        "When tasks are ambiguous, make a reasonable assumption and continue."
    ),
    max_tool_rounds=10,
)


MINIAGENT_LIKE = AgentProfile(
    name="miniagent_like",
    system_prompt=(
        "You are a fast, practical assistant. Keep responses concise and action-oriented. "
        "Use tools only when needed and avoid over-planning. "
        "Execute quickly and return the key result."
    ),
    max_tool_rounds=6,
)


AGENTS = {
    MANUS_LIKE.name: MANUS_LIKE,
    MINIAGENT_LIKE.name: MINIAGENT_LIKE,
}


def get_agent(name: str) -> AgentProfile:
    if name not in AGENTS:
        options = ", ".join(sorted(AGENTS.keys()))
        raise ValueError(f"Unknown agent '{name}'. Available: {options}")
    return AGENTS[name]
