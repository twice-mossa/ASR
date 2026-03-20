from __future__ import annotations

import logging

from fastapi import HTTPException

from app.ai_runtime.qa_graph import ask_meeting_question_with_graph
from app.core.config import settings
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingAskResponse
from app.services.qa_legacy_service import ask_meeting_question_legacy

logger = logging.getLogger(__name__)


async def ask_meeting_question(meeting_id: int, question: str, current_user: UserProfile) -> MeetingAskResponse:
    use_langgraph = settings.ai_runtime_enabled and (settings.qa_engine or "legacy").lower() == "langgraph"
    if not use_langgraph:
        return await ask_meeting_question_legacy(meeting_id, question, current_user)

    try:
        return await ask_meeting_question_with_graph(meeting_id, question, current_user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("LangGraph QA failed, falling back to legacy QA: %s", exc)
        return await ask_meeting_question_legacy(meeting_id, question, current_user)
