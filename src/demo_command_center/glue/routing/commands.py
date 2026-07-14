from __future__ import annotations

from enum import StrEnum


class ConversationCommand(StrEnum):
    HELP = "HELP"
    BACK = "BACK"
    CANCEL = "CANCEL"
    RESCHEDULE = "RESCHEDULE"
    RESTART = "RESTART"
    HUMAN = "HUMAN"
    STATUS = "STATUS"
    STOP = "STOP"


_ALIASES = {
    "UNSUBSCRIBE": ConversationCommand.STOP,
    "QUIT": ConversationCommand.STOP,
}


def parse_conversation_command(user_text: str | None) -> ConversationCommand | None:
    """Parse only a complete user token; content is never executed as an instruction."""

    if user_text is None:
        return None
    normalized = " ".join(user_text.strip().upper().split())
    if normalized in _ALIASES:
        return _ALIASES[normalized]
    try:
        return ConversationCommand(normalized)
    except ValueError:
        return None
