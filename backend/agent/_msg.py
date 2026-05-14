"""Message helpers — handle both raw dicts (direct node tests) and
LangChain BaseMessage objects (when invoked through StateGraph with
add_messages reducer)."""


def msg_content(m) -> str:
    """Extract 'content' from a message that is either a dict or a BaseMessage."""
    if isinstance(m, dict):
        return m.get("content", "")
    return getattr(m, "content", "")


def msg_role(m) -> str:
    """Extract 'role' from a message that is either a dict or a BaseMessage.

    LangGraph converts ``{"role": "user"}`` → ``HumanMessage(type="human")``,
    ``{"role": "assistant"}`` → ``AIMessage(type="ai")``, etc.
    """
    if isinstance(m, dict):
        return m.get("role", "user")
    return getattr(m, "type", "human")


def last_msg_content(state: dict, default: str = "") -> str:
    """Shortcut: content of the most recent message in *state*, or *default*."""
    msgs = state.get("messages", [])
    if not msgs:
        return default
    return msg_content(msgs[-1])
