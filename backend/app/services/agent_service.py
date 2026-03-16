"""
Meeting Analysis Agent
======================
Replaces the single-turn LLM call with an iterative tool-calling agent.

The agent owns a small set of analysis tools and calls them one by one to
produce a richer, more structured meeting report:
  - extract_summary        → concise meeting summary
  - extract_key_decisions  → formal decisions reached in the meeting
  - extract_action_items   → tasks with optional owner + deadline
  - extract_keywords       → important terms / jargon
  - finish_report          → overall meeting assessment

The loop continues until the model calls finish_report or runs out of steps.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.meeting import ActionItem, AgentMeetingReport

logger = logging.getLogger(__name__)

_MAX_AGENT_STEPS = 10  # guard against runaway loops

_AGENT_SYSTEM_PROMPT = (
    "你是一个专业的会议分析 Agent，拥有多个结构化分析工具。\n"
    "请按以下顺序依次调用工具，每次只调用一个：\n"
    "1. extract_summary       — 生成会议摘要\n"
    "2. extract_key_decisions — 提取关键决策\n"
    "3. extract_action_items  — 提取行动项\n"
    "4. extract_keywords      — 提取关键词\n"
    "5. finish_report         — 汇总整体评估，结束分析\n"
    "完成所有工具调用后不需要再输出任何解释性文字。"
)

_AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "extract_summary",
            "description": "从会议转写文本中提取简明的会议摘要，概括主要议题和讨论内容，不超过 300 字。",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "会议摘要文本。",
                    },
                },
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_key_decisions",
            "description": "从会议转写文本中提取所有正式决议和关键决定，每条为完整句子。",
            "parameters": {
                "type": "object",
                "properties": {
                    "decisions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关键决策列表。",
                    },
                },
                "required": ["decisions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_action_items",
            "description": (
                "从会议转写文本中提取所有待办事项和行动项，"
                "尽量记录负责人和截止时间（若转写中未提及则留空字符串）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string", "description": "任务描述"},
                                "owner": {"type": "string", "description": "负责人，未提及则为空字符串"},
                                "deadline": {"type": "string", "description": "截止时间，未提及则为空字符串"},
                            },
                            "required": ["task", "owner", "deadline"],
                        },
                        "description": "行动项列表。",
                    },
                },
                "required": ["action_items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_keywords",
            "description": "从会议转写文本中提取 5-10 个最重要的关键词和专业术语。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关键词列表。",
                    },
                },
                "required": ["keywords"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_report",
            "description": "所有分析工具调用完毕后，对本次会议进行整体评估并结束 Agent 分析流程。",
            "parameters": {
                "type": "object",
                "properties": {
                    "overall_assessment": {
                        "type": "string",
                        "description": "对会议整体的简要评估，如会议效率、议题完整度、后续跟进建议等。",
                    },
                },
                "required": ["overall_assessment"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Internal tool executor
# ---------------------------------------------------------------------------


def _execute_tool(name: str, args: dict[str, Any], accumulated: dict[str, Any]) -> dict[str, Any]:
    """
    'Execute' a tool call.  For analysis tools the LLM already provides the
    structured data as arguments, so execution just means storing those results
    and returning a short confirmation message back to the model.
    """
    if name == "extract_summary":
        accumulated["summary"] = str(args.get("summary") or "")
        return {"status": "ok", "message": "会议摘要已记录。"}

    if name == "extract_key_decisions":
        accumulated["key_decisions"] = [str(d) for d in (args.get("decisions") or [])]
        return {"status": "ok", "message": f"已记录 {len(accumulated['key_decisions'])} 条关键决策。"}

    if name == "extract_action_items":
        raw_items = args.get("action_items") or []
        accumulated["action_items"] = [
            {
                "task": str(item.get("task") or ""),
                "owner": str(item.get("owner") or ""),
                "deadline": str(item.get("deadline") or ""),
            }
            for item in raw_items
            if isinstance(item, dict)
        ]
        return {"status": "ok", "message": f"已记录 {len(accumulated['action_items'])} 条行动项。"}

    if name == "extract_keywords":
        accumulated["keywords"] = [str(k) for k in (args.get("keywords") or [])]
        return {"status": "ok", "message": f"已记录 {len(accumulated['keywords'])} 个关键词。"}

    if name == "finish_report":
        accumulated["overall_assessment"] = str(args.get("overall_assessment") or "")
        return {"status": "ok", "message": "报告已汇总，分析结束。"}

    logger.warning("Agent called unknown tool: %s", name)
    return {"status": "unknown_tool", "message": f"未知工具: {name}"}


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


def _fallback_agent_report(text: str) -> AgentMeetingReport:
    """Simple rule-based fallback when the API is unavailable."""
    import re

    logger.warning("Using fallback agent report (API unavailable).")
    zh_tokens = re.findall(r"[\u4e00-\u9fa5]{2,}", text or "")
    en_tokens = re.findall(r"[A-Za-z]{4,}", text or "")
    freq: dict[str, int] = {}
    for t in zh_tokens + [e.lower() for e in en_tokens]:
        freq[t] = freq.get(t, 0) + 1
    keywords = [k for k, _ in sorted(freq.items(), key=lambda x: (-x[1], -len(x[0])))[:8]]

    summary_text = (text or "").strip()
    if len(summary_text) > 200:
        summary_text = summary_text[:200] + "..."

    return AgentMeetingReport(
        summary=summary_text,
        key_decisions=[],
        action_items=[ActionItem(task="整理并确认会议记录", owner="", deadline="")],
        keywords=keywords or ["会议", "记录"],
        overall_assessment="（MiniMax API 不可用，已使用本地规则生成基础报告）",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_meeting_agent(text: str) -> AgentMeetingReport:
    """
    Run a tool-calling agent that systematically analyzes the meeting transcript.

    The agent sends the transcript to MiniMax, receives tool calls, executes
    them locally, feeds the results back, and repeats until finish_report is
    called or the step budget is exhausted.
    """
    if not text:
        return _fallback_agent_report("")

    if not settings.minimax_api_key:
        logger.warning("MiniMax API key not set. Returning fallback agent report.")
        return _fallback_agent_report(text)

    base_url = getattr(settings, "minimax_base_url", "https://api.minimaxi.com/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}",
        "Content-Type": "application/json",
    }

    # Holds structured data collected across tool calls
    accumulated: dict[str, Any] = {
        "summary": "",
        "key_decisions": [],
        "action_items": [],
        "keywords": [],
        "overall_assessment": "",
    }

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"请分析以下会议转写文本：\n\n{text}"},
    ]

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        for step in range(_MAX_AGENT_STEPS):
            logger.info("Agent step %s/%s", step + 1, _MAX_AGENT_STEPS)

            data: dict[str, Any] = {
                "model": "MiniMax-M2.5",
                "temperature": 0.1,
                "messages": messages,
                "tools": _AGENT_TOOLS,
                "tool_choice": "auto",
            }

            try:
                resp = await client.post(url, headers=headers, json=data)
                resp.raise_for_status()
            except Exception as exc:
                logger.exception("Agent step %s API call failed: %s", step + 1, exc)
                return _fallback_agent_report(text)

            body: dict[str, Any] = resp.json()
            choices = body.get("choices") or []
            if not choices:
                logger.error("Empty choices from API at step %s", step + 1)
                break

            choice = choices[0]
            msg = choice.get("message") or {}
            finish_reason = choice.get("finish_reason", "")

            # Append the assistant turn (preserve tool_calls list for history)
            assistant_turn: dict[str, Any] = {
                "role": "assistant",
                "content": msg.get("content") or "",
            }
            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                assistant_turn["tool_calls"] = tool_calls
            messages.append(assistant_turn)

            if not tool_calls:
                # No tool calls — the agent has finished
                break

            # Execute each tool call and return results
            done = False
            for tc in tool_calls:
                tc_id = tc.get("id", "")
                function = tc.get("function") or {}
                fn_name = function.get("name", "")
                fn_args_raw = function.get("arguments", "{}")

                try:
                    fn_args = json.loads(fn_args_raw)
                except json.JSONDecodeError:
                    fn_args = {}

                tool_result = _execute_tool(fn_name, fn_args, accumulated)
                logger.info("Tool %s → %s", fn_name, tool_result.get("message"))

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

                if fn_name == "finish_report":
                    done = True

            if done or finish_reason == "stop":
                break

    return AgentMeetingReport(
        summary=accumulated["summary"],
        key_decisions=accumulated["key_decisions"],
        action_items=[ActionItem(**item) for item in accumulated["action_items"]],
        keywords=accumulated["keywords"],
        overall_assessment=accumulated["overall_assessment"],
    )
