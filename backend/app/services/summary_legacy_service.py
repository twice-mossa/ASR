from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingSummaryResponse
from app.services.email_service import maybe_auto_send_summary_email
from app.services.meeting_service import get_meeting_transcript_text, save_meeting_summary, update_meeting_status

logger = logging.getLogger(__name__)


def fallback_summarize(text: str) -> MeetingSummaryResponse:
    logger.warning("Using fallback summarization logic.")
    base_summary = (text or "").strip()
    if len(base_summary) > 180:
        base_summary = base_summary[:180] + "..."

    zh_tokens = re.findall(r"[\u4e00-\u9fa5]{2,}", text or "")
    en_tokens = re.findall(r"[A-Za-z]{4,}", text or "")
    freq: dict[str, int] = {}
    for token in zh_tokens + [item.lower() for item in en_tokens]:
        freq[token] = freq.get(token, 0) + 1

    keywords = sorted(freq.items(), key=lambda item: (-item[1], -len(item[0])))[:8]
    keywords_list = [key for key, _ in keywords]
    if not keywords_list:
        keywords_list = ["会议", "摘要", "记录"]

    todos = [
        "确认转写文本是否准确",
        "整理会议纪要",
    ]
    return MeetingSummaryResponse(summary=base_summary, keywords=keywords_list, todos=todos)


async def build_summary_legacy(text: str) -> MeetingSummaryResponse:
    if not text:
        return fallback_summarize("")

    if not settings.minimax_api_key:
        logger.warning("MiniMax API key not set. Using fallback.")
        return fallback_summarize(text)

    base_url = getattr(settings, "minimax_base_url", "https://api.minimaxi.com/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}",
        "Content-Type": "application/json",
    }
    system_prompt = (
        "你是一个专业的会议助理。请根据用户提供的会议转写文本，生成以下三部分内容：\n"
        "1. 会议摘要 (summary)：简明扼要地总结会议内容。\n"
        "2. 核心关键词 (keywords)：提取5-8个关键术语。\n"
        "3. 待办事项 (todos)：列出具体的行动项。\n\n"
        "请严格输出 JSON 格式，格式如下：\n"
        '{"summary": "...", "keywords": ["...", "..."], "todos": ["...", "..."]}\n'
        "不要输出任何其他解释性文字。"
    )
    user_prompt = f"以下是会议转写文本：\n{text}"
    data = {
        "model": "MiniMax-M2.5",
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            body: dict[str, Any] = response.json()
    except Exception as exc:
        logger.exception("MiniMax API call failed: %s", exc)
        return fallback_summarize(text)

    content = None
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) or {}
        content = message.get("content")
    if not content and "output" in body:
        content = body["output"]
    if not content:
        return fallback_summarize(text)

    cleaned = str(content).strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    parsed = None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                parsed = None

    if parsed is None:
        logger.error("Failed to parse JSON from model output: %s", content)
        return fallback_summarize(text)

    return MeetingSummaryResponse(
        summary=str(parsed.get("summary") or "").strip() or text[:200],
        keywords=[str(item) for item in (parsed.get("keywords") or [])],
        todos=[str(item) for item in (parsed.get("todos") or [])],
    )


async def build_summary_for_meeting_legacy(meeting_id: int, current_user: UserProfile) -> MeetingSummaryResponse:
    text = get_meeting_transcript_text(meeting_id, current_user)
    summary = await build_summary_legacy(text)
    save_meeting_summary(meeting_id, summary)
    update_meeting_status(meeting_id, status_value="summarized", error_message="")
    await asyncio.to_thread(maybe_auto_send_summary_email, meeting_id, current_user)
    return summary
