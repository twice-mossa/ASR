from __future__ import annotations

import asyncio
import json
import re
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.meeting import MeetingSummaryResponse

logger = logging.getLogger(__name__)

def _fallback_summarize(text: str) -> MeetingSummaryResponse:
    """
    Simple rule-based fallback if API call fails.
    """
    logger.warning("Using fallback summarization logic.")
    base_summary = (text or "").strip()
    if len(base_summary) > 180:
        base_summary = base_summary[:180] + "..."
    
    # Extract potential keywords (simple heuristic)
    zh_tokens = re.findall(r"[\u4e00-\u9fa5]{2,}", text or "")
    en_tokens = re.findall(r"[A-Za-z]{4,}", text or "")
    freq: dict[str, int] = {}
    for t in zh_tokens + [e.lower() for e in en_tokens]:
        freq[t] = freq.get(t, 0) + 1
    
    keywords = sorted(freq.items(), key=lambda x: (-x[1], -len(x[0])))[:8]
    keywords_list = [k for k, _ in keywords]
    if not keywords_list:
        keywords_list = ["会议", "摘要", "记录"]

    todos = [
        "确认转写文本是否准确",
        "整理会议纪要",
    ]
    
    return MeetingSummaryResponse(summary=base_summary, keywords=keywords_list, todos=todos)


async def build_summary(text: str) -> MeetingSummaryResponse:
    """
    Call MiniMax API to generate meeting summary, keywords, and TODOs.
    """
    if not text:
        return _fallback_summarize("")

    if not settings.minimax_api_key:
        logger.warning("MiniMax API key not set. Using fallback.")
        return _fallback_summarize(text)

    # Coding Plan keys follow the current OpenAI-compatible MiniMax endpoint.
    base_url = getattr(settings, "minimax_base_url", "https://api.minimaxi.com/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}", 
        "Content-Type": "application/json"
    }
    
    # Construct Prompt
    system_prompt = (
        "你是一个专业的会议助理。请根据用户提供的会议转写文本，生成以下三部分内容：\n"
        "1. 会议摘要 (summary)：简明扼要地总结会议内容。\n"
        "2. 核心关键词 (keywords)：提取5-8个关键术语。\n"
        "3. 待办事项 (todos)：列出具体的行动项。\n\n"
        "请严格输出 JSON 格式，格式如下：\n"
        '{"summary": "...", "keywords": ["...", "..."], "todos": ["...", "..."]}\n'
        "不要输出任何其他解释性文字。"
    )
    
    return await build_summary_with_guidance(text, system_prompt)


async def build_summary_with_guidance(text: str, guidance: str) -> MeetingSummaryResponse:
    if not text:
        return _fallback_summarize("")

    if not settings.minimax_api_key:
        logger.warning("MiniMax API key not set. Using fallback.")
        return _fallback_summarize(text)

    base_url = getattr(settings, "minimax_base_url", "https://api.minimaxi.com/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}",
        "Content-Type": "application/json",
    }

    structured_guidance = (
        f"{guidance}\n\n"
        "请严格输出 JSON 格式，格式如下：\n"
        '{"summary": "...", "keywords": ["...", "..."], "todos": ["...", "..."]}\n'
        "不要输出任何其他解释性文字。"
    )

    user_prompt = f"以下是会议转写文本：\n{text}"

    data = {
        "model": "MiniMax-M2.5",
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": structured_guidance},
            {"role": "user", "content": user_prompt},
        ],
        # Some providers support response_format={"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(url, headers=headers, json=data)
            resp.raise_for_status()
            
            body: dict[str, Any] = resp.json()
            content = None
            
            # Parse OpenAI-compatible response
            choices = body.get("choices")
            if isinstance(choices, list) and choices:
                msg = choices[0].get("message", {}) or {}
                content = msg.get("content")
            
            # Fallback for other potential response shapes
            if not content and "output" in body:
                content = body["output"]
                
            if not content:
                logger.error("Empty content from MiniMax API")
                return _fallback_summarize(text)
                
            # Parse JSON content
            # Clean up code blocks if model outputs them
            cleaned_content = content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            if cleaned_content.startswith("```"):
                cleaned_content = cleaned_content[3:]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            
            cleaned_content = cleaned_content.strip()

            parsed = None
            try:
                parsed = json.loads(cleaned_content)
            except json.JSONDecodeError:
                start = cleaned_content.find("{")
                end = cleaned_content.rfind("}")
                if start != -1 and end != -1 and end > start:
                    candidate = cleaned_content[start : end + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        parsed = None

            if parsed is None:
                logger.error(f"Failed to parse JSON from model output: {content}")
                return _fallback_summarize(text)

            return MeetingSummaryResponse(
                summary=str(parsed.get("summary") or "").strip() or text[:200],
                keywords=[str(k) for k in (parsed.get("keywords") or [])],
                todos=[str(t) for t in (parsed.get("todos") or [])],
            )
            
    except Exception as e:
        logger.exception(f"MiniMax API call failed: {e}")
        return _fallback_summarize(text)
