import unittest
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingAskResponse, MeetingCitation, MeetingSummaryResponse
from app.services.minimax_service import build_summary
from app.services.qa_service import ask_meeting_question


class AIRuntimeRoutingTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_ai_runtime_enabled = settings.ai_runtime_enabled
        self.original_summary_engine = settings.summary_engine
        self.original_qa_engine = settings.qa_engine
        settings.ai_runtime_enabled = True

    def tearDown(self):
        settings.ai_runtime_enabled = self.original_ai_runtime_enabled
        settings.summary_engine = self.original_summary_engine
        settings.qa_engine = self.original_qa_engine

    async def test_summary_uses_langgraph_when_enabled(self):
        settings.summary_engine = "langgraph"
        payload = MeetingSummaryResponse(summary="图摘要", keywords=["LangGraph"], todos=["验证"])

        with patch("app.services.minimax_service.build_summary_with_graph", new=AsyncMock(return_value=payload)) as graph_mock:
            result = await build_summary("这里是一段会议转写")

        self.assertEqual(result.summary, "图摘要")
        graph_mock.assert_awaited_once()

    async def test_summary_falls_back_to_legacy_when_graph_fails(self):
        settings.summary_engine = "langgraph"
        legacy_payload = MeetingSummaryResponse(summary="旧摘要", keywords=["legacy"], todos=["回退"])

        with patch(
            "app.services.minimax_service.build_summary_with_graph",
            new=AsyncMock(side_effect=RuntimeError("graph failed")),
        ), patch(
            "app.services.minimax_service.build_summary_legacy",
            new=AsyncMock(return_value=legacy_payload),
        ) as legacy_mock:
            result = await build_summary("这里是一段会议转写")

        self.assertEqual(result.summary, "旧摘要")
        legacy_mock.assert_awaited_once()

    async def test_qa_uses_langgraph_when_enabled(self):
        settings.qa_engine = "langgraph"
        payload = MeetingAskResponse(
            answer="图问答结果",
            citations=[MeetingCitation(text="依据", start=0.0, end=1.0, segment_id=1)],
            reasoning_summary="图工作流命中引用",
        )
        user = UserProfile(id=1, username="tester", email="tester@example.com")

        with patch("app.services.qa_service.ask_meeting_question_with_graph", new=AsyncMock(return_value=payload)) as graph_mock:
            result = await ask_meeting_question(1, "会议重点是什么？", user)

        self.assertEqual(result.answer, "图问答结果")
        graph_mock.assert_awaited_once()

    async def test_qa_falls_back_to_legacy_when_graph_fails(self):
        settings.qa_engine = "langgraph"
        legacy_payload = MeetingAskResponse(
            answer="旧问答结果",
            citations=[],
            reasoning_summary="已回退 legacy",
        )
        user = UserProfile(id=1, username="tester", email="tester@example.com")

        with patch(
            "app.services.qa_service.ask_meeting_question_with_graph",
            new=AsyncMock(side_effect=RuntimeError("graph failed")),
        ), patch(
            "app.services.qa_service.ask_meeting_question_legacy",
            new=AsyncMock(return_value=legacy_payload),
        ) as legacy_mock:
            result = await ask_meeting_question(1, "会议重点是什么？", user)

        self.assertEqual(result.answer, "旧问答结果")
        legacy_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
