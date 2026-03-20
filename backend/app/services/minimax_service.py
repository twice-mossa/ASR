from __future__ import annotations

import asyncio
import logging

from app.ai_runtime.summary_graph import build_summary_with_graph
from app.core.config import settings
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingSummaryResponse
from app.services.email_service import maybe_auto_send_summary_email
from app.services.meeting_service import get_meeting_transcript_text
from app.services.summary_legacy_service import build_summary_for_meeting_legacy, build_summary_legacy, fallback_summarize

logger = logging.getLogger(__name__)


async def build_summary(text: str) -> MeetingSummaryResponse:
    if not text:
        return fallback_summarize("")

    use_langgraph = settings.ai_runtime_enabled and (settings.summary_engine or "legacy").lower() == "langgraph"
    if not use_langgraph:
        return await build_summary_legacy(text)

    try:
        return await build_summary_with_graph(text=text)
    except Exception as exc:
        logger.exception("LangGraph summary failed, falling back to legacy summary: %s", exc)
        return await build_summary_legacy(text)


async def build_summary_for_meeting(meeting_id: int, current_user: UserProfile) -> MeetingSummaryResponse:
    use_langgraph = settings.ai_runtime_enabled and (settings.summary_engine or "legacy").lower() == "langgraph"
    if not use_langgraph:
        return await build_summary_for_meeting_legacy(meeting_id, current_user)

    try:
        transcript_text = get_meeting_transcript_text(meeting_id, current_user)
        summary = await build_summary_with_graph(
            text=transcript_text,
            meeting_id=meeting_id,
            current_user=current_user,
        )
        await asyncio.to_thread(maybe_auto_send_summary_email, meeting_id, current_user)
        return summary
    except Exception as exc:
        logger.exception("LangGraph meeting summary failed, falling back to legacy summary: %s", exc)
        return await build_summary_for_meeting_legacy(meeting_id, current_user)
