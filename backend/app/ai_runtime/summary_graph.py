from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai_runtime.providers import chat_model_for_summary
from app.ai_runtime.schemas import SummaryStructuredOutput
from app.core.config import settings
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingSummaryResponse
from app.services.meeting_service import get_meeting_transcript_text, save_meeting_summary, update_meeting_status

logger = logging.getLogger(__name__)
_MAX_SUMMARY_CONTEXT = 12000


class SummaryState(TypedDict, total=False):
    meeting_id: int | None
    current_user: UserProfile | None
    transcript_text: str
    compressed_text: str
    provider_config: dict[str, str]
    summary: str
    keywords: list[str]
    todos: list[str]
    errors: list[str]


def _compress_transcript(text: str) -> str:
    normalized = (text or "").strip()
    if len(normalized) <= _MAX_SUMMARY_CONTEXT:
        return normalized

    chunk = _MAX_SUMMARY_CONTEXT // 3
    middle_start = max(0, len(normalized) // 2 - chunk // 2)
    middle_end = middle_start + chunk
    head = normalized[:chunk]
    middle = normalized[middle_start:middle_end]
    tail = normalized[-chunk:]
    return "\n...\n".join([head.strip(), middle.strip(), tail.strip()])


def _load_meeting_context(state: SummaryState) -> SummaryState:
    transcript_text = (state.get("transcript_text") or "").strip()
    meeting_id = state.get("meeting_id")
    current_user = state.get("current_user")
    if not transcript_text and meeting_id is not None and current_user is not None:
        transcript_text = get_meeting_transcript_text(meeting_id, current_user)
    return {
        "transcript_text": transcript_text,
        "provider_config": {
            "kind": "langgraph",
            "task": "summary",
        },
    }


def _chunk_or_compress_transcript(state: SummaryState) -> SummaryState:
    return {"compressed_text": _compress_transcript(state.get("transcript_text") or "")}


def _message_content_to_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def _parse_structured_text(schema, raw_text: str):
    cleaned = str(raw_text or "").strip()
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return schema.model_validate_json(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return schema.model_validate_json(cleaned[start : end + 1])
        raise


async def _invoke_summary_structured_output(schema, prompt):
    llm = chat_model_for_summary()
    provider = (settings.chat_provider or "").strip().lower()
    if provider != "minimax":
        try:
            return await llm.with_structured_output(schema).ainvoke(prompt)
        except Exception:
            raw = await llm.ainvoke(prompt)
            return _parse_structured_text(schema, _message_content_to_text(raw))

    raw = await llm.ainvoke(prompt)
    return _parse_structured_text(schema, _message_content_to_text(raw))


async def _generate_structured_summary(state: SummaryState) -> SummaryState:
    prompt = [
        (
            "system",
            "你是一个专业的会议助理。请基于提供的会议转写文本，输出结构化会议纪要。"
            "要求：summary 用简洁中文概括会议结论；keywords 提取 5-8 个关键术语；"
            "todos 只输出明确行动项。不要输出与 schema 无关的内容。"
            "只输出一个 JSON 对象，不要解释、不要 markdown。"
            'JSON 结构必须是：{"summary":"...","keywords":["..."],"todos":["..."]}',
        ),
        (
            "human",
            f"会议转写文本：\n{state.get('compressed_text') or state.get('transcript_text') or ''}",
        ),
    ]
    result = await _invoke_summary_structured_output(SummaryStructuredOutput, prompt)
    return {
        "summary": result.summary.strip(),
        "keywords": [item.strip() for item in result.keywords if item.strip()],
        "todos": [item.strip() for item in result.todos if item.strip()],
    }


def _validate_summary_shape(state: SummaryState) -> SummaryState:
    transcript_text = state.get("transcript_text") or ""
    summary = (state.get("summary") or "").strip() or transcript_text[:200].strip()
    keywords = []
    seen_keywords: set[str] = set()
    for keyword in state.get("keywords") or []:
        normalized = keyword.strip()
        if normalized and normalized not in seen_keywords:
            seen_keywords.add(normalized)
            keywords.append(normalized)

    todos = []
    seen_todos: set[str] = set()
    for todo in state.get("todos") or []:
        normalized = todo.strip()
        if normalized and normalized not in seen_todos:
            seen_todos.add(normalized)
            todos.append(normalized)

    if not keywords:
        keywords = ["会议", "摘要", "记录"]
    if not todos:
        todos = ["确认转写文本是否准确", "整理会议纪要"]

    return {
        "summary": summary,
        "keywords": keywords[:8],
        "todos": todos[:8],
    }


def _persist_summary(state: SummaryState) -> SummaryState:
    meeting_id = state.get("meeting_id")
    if meeting_id is not None:
        payload = MeetingSummaryResponse(
            summary=state.get("summary") or "",
            keywords=state.get("keywords") or [],
            todos=state.get("todos") or [],
        )
        save_meeting_summary(meeting_id, payload)
        update_meeting_status(meeting_id, status_value="summarized", error_message="")
    return {}


@lru_cache(maxsize=1)
def get_summary_graph():
    builder = StateGraph(SummaryState)
    builder.add_node("load_meeting_context", _load_meeting_context)
    builder.add_node("chunk_or_compress_transcript", _chunk_or_compress_transcript)
    builder.add_node("generate_structured_summary", _generate_structured_summary)
    builder.add_node("validate_summary_shape", _validate_summary_shape)
    builder.add_node("persist_summary", _persist_summary)
    builder.add_edge(START, "load_meeting_context")
    builder.add_edge("load_meeting_context", "chunk_or_compress_transcript")
    builder.add_edge("chunk_or_compress_transcript", "generate_structured_summary")
    builder.add_edge("generate_structured_summary", "validate_summary_shape")
    builder.add_edge("validate_summary_shape", "persist_summary")
    builder.add_edge("persist_summary", END)
    return builder.compile()


async def build_summary_with_graph(
    *,
    text: str = "",
    meeting_id: int | None = None,
    current_user: UserProfile | None = None,
) -> MeetingSummaryResponse:
    graph = get_summary_graph()
    state = await graph.ainvoke(
        {
            "meeting_id": meeting_id,
            "current_user": current_user,
            "transcript_text": text,
            "errors": [],
        }
    )
    return MeetingSummaryResponse(
        summary=state.get("summary") or "",
        keywords=state.get("keywords") or [],
        todos=state.get("todos") or [],
    )
