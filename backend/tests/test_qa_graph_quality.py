import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

_TEST_DIR = Path(tempfile.mkdtemp(prefix="asr-qa-graph-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'qa_graph_test.db'}"
os.environ["UPLOAD_DIR"] = str(_TEST_DIR / "uploads")
os.environ["AI_RUNTIME_ENABLED"] = "true"
os.environ["SUMMARY_ENGINE"] = "langgraph"
os.environ["QA_ENGINE"] = "langgraph"
os.environ["EMBEDDING_PROVIDER"] = "sentence_transformers"
os.environ["EMBEDDING_MODEL"] = "BAAI/bge-small-zh-v1.5"

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.ai_runtime.qa_graph import get_qa_graph
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import Meeting, MeetingQARecord, MeetingSummary, TranscriptSegment, User
from app.schemas.auth import UserProfile
from app.services.auth_service import _SESSIONS


class _FakeStructuredRunnable:
    def __init__(self, schema):
        self.schema = schema

    async def ainvoke(self, prompt):
        name = self.schema.__name__
        if name == "QuestionIntent":
            return self.schema(
                question_type="fact",
                rewritten_question="会议里关于充电宝的讨论是什么",
                entities=["充电宝", "大容量", "安全认证"],
                anchors=[],
                use_recent_history=False,
            )
        if name == "RerankedEvidenceWindows":
            return self.schema(
                ordered_window_ids=[1],
                reasoning_summary="优先保留直接讨论充电宝卖点的窗口。",
            )
        if name == "GroundedAnswerStructuredOutput":
            return self.schema(
                answer="会议明确提到，充电宝卖点要突出大容量和安全认证。",
                reasoning_summary="相关片段直接讨论了充电宝的主打卖点。",
                citation_window_ids=[1],
            )
        if name == "GroundedAnswerCheck":
            return self.schema(
                grounded=True,
                answer="会议明确提到，充电宝卖点要突出大容量和安全认证。",
                reasoning_summary="证据窗口里直接出现了充电宝、大容量和安全认证。",
                citation_window_ids=[1],
                insufficiency_reason="",
            )
        raise AssertionError(f"Unexpected schema: {name}")


class _FakeChatModel:
    def with_structured_output(self, schema):
        return _FakeStructuredRunnable(schema)

    async def ainvoke(self, prompt):
        text = "\n".join(part[1] for part in prompt if isinstance(part, tuple) and len(part) > 1)
        if "question_type" in text and "rewritten_question" in text:
            return type(
                "FakeMessage",
                (),
                {
                    "content": (
                        '{"question_type":"fact","rewritten_question":"会议里关于充电宝的讨论是什么",'
                        '"entities":["充电宝","大容量","安全认证"],"anchors":[],"use_recent_history":false}'
                    )
                },
            )()
        if "ordered_window_ids" in text:
            return type("FakeMessage", (), {"content": '{"ordered_window_ids":[1],"reasoning_summary":"优先保留充电宝卖点窗口。"}'})()
        if '"grounded":true' in text:
            return type(
                "FakeMessage",
                (),
                {
                    "content": (
                        '{"grounded":true,"answer":"会议明确提到，充电宝卖点要突出大容量和安全认证。",'
                        '"reasoning_summary":"证据窗口里直接出现了充电宝、大容量和安全认证。",'
                        '"citation_window_ids":[1],"insufficiency_reason":""}'
                    )
                },
            )()
        return type(
            "FakeMessage",
            (),
            {
                "content": (
                    '{"answer":"会议明确提到，充电宝卖点要突出大容量和安全认证。",'
                    '"reasoning_summary":"相关片段直接讨论了充电宝的主打卖点。","citation_window_ids":[1]}'
                )
            },
        )()


class QAGraphQualityTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.original_embedding_provider = settings.embedding_provider
        self.original_qa_require_real_embeddings = settings.qa_require_real_embeddings
        self.original_ai_runtime_enabled = settings.ai_runtime_enabled
        self.original_qa_engine = settings.qa_engine
        settings.embedding_provider = "sentence_transformers"
        settings.qa_require_real_embeddings = True
        settings.ai_runtime_enabled = True
        settings.qa_engine = "langgraph"

        _SESSIONS.clear()
        get_qa_graph.cache_clear()

        with SessionLocal() as db:
            db.execute(delete(MeetingQARecord))
            db.execute(delete(MeetingSummary))
            db.execute(delete(TranscriptSegment))
            db.execute(delete(Meeting))
            db.execute(delete(User))
            db.add(
                User(
                    id=1,
                    username="qa-graph",
                    email="qa-graph@example.com",
                    password_salt="salt",
                    password_hash="hash",
                )
            )
            db.commit()
            db.add(
                Meeting(
                    id=1,
                    user_id=1,
                    title="产品讨论会",
                    filename="product.wav",
                    stored_filename="product.wav",
                    audio_path=str((_TEST_DIR / "uploads" / "product.wav").resolve()),
                    content_type="audio/wav",
                    duration_label="00:45",
                    language="zh",
                    status="summarized",
                    transcript_text=(
                        "今天先讨论销售平台。关于充电宝，大家认为要突出大容量和安全认证。"
                        "包装设计暂时不做大改。下周再确认发售节奏。"
                    ),
                )
            )
            db.add_all(
                [
                    TranscriptSegment(meeting_id=1, start=0.0, end=6.0, text="今天先讨论销售平台。"),
                    TranscriptSegment(meeting_id=1, start=6.0, end=14.0, text="关于充电宝，大家认为要突出大容量和安全认证。"),
                    TranscriptSegment(meeting_id=1, start=14.0, end=20.0, text="包装设计暂时不做大改。"),
                    TranscriptSegment(meeting_id=1, start=20.0, end=26.0, text="下周再确认发售节奏。"),
                ]
            )
            db.add(
                MeetingSummary(
                    meeting_id=1,
                    summary="会议讨论了销售平台、充电宝卖点和后续发售节奏。",
                    keywords_json='["销售平台","充电宝","安全认证"]',
                    todos_json='["确认发售节奏"]',
                )
            )
            db.commit()

        _SESSIONS["qa-graph-token"] = UserProfile(id=1, username="qa-graph", email="qa-graph@example.com")

    def tearDown(self):
        settings.embedding_provider = self.original_embedding_provider
        settings.qa_require_real_embeddings = self.original_qa_require_real_embeddings
        settings.ai_runtime_enabled = self.original_ai_runtime_enabled
        settings.qa_engine = self.original_qa_engine
        get_qa_graph.cache_clear()

    def test_hybrid_retrieval_keeps_relevant_charge_bank_evidence(self):
        fake_docs = [
            Document(page_content="包装设计暂时不做大改。", metadata={"segment_id": 3}),
        ]
        with patch("app.ai_runtime.qa_graph._ensure_qa_runtime_ready"), patch(
            "app.ai_runtime.qa_graph.ensure_meeting_index"
        ), patch("app.ai_runtime.qa_graph.retrieve_meeting_segments", return_value=fake_docs), patch(
            "app.ai_runtime.qa_graph.chat_model_for_qa",
            return_value=_FakeChatModel(),
        ):
            response = self.client.post(
                "/api/meetings/1/ask",
                json={"question": "关于充电宝说了什么？"},
                headers={"Authorization": "Bearer qa-graph-token"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("充电宝", body["answer"])
        self.assertIn("大容量", body["answer"])
        self.assertNotIn("我先根据当前会议里检索到的相关片段回答", body["answer"])
        self.assertTrue(body["citations"])
        joined_citations = "\n".join(item["text"] for item in body["citations"])
        self.assertIn("充电宝", joined_citations)
        self.assertIn("安全认证", joined_citations)

    def test_langgraph_qa_requires_real_embeddings(self):
        settings.embedding_provider = "local"
        settings.qa_require_real_embeddings = True

        response = self.client.post(
            "/api/meetings/1/ask",
            json={"question": "会议提到了什么？"},
            headers={"Authorization": "Bearer qa-graph-token"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("embedding", response.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
