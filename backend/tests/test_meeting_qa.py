import os
import tempfile
import unittest
from pathlib import Path

_TEST_DIR = Path(tempfile.mkdtemp(prefix="asr-qa-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'meeting_qa_test.db'}"
os.environ["UPLOAD_DIR"] = str(_TEST_DIR / "uploads")

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import Meeting, MeetingQARecord, MeetingSummary, TranscriptSegment, User
from app.schemas.auth import UserProfile
from app.services.auth_service import _SESSIONS


class MeetingQATestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.token = "test-token"
        self.user_id = 101
        self.meeting_id = 201
        _SESSIONS.clear()

        with SessionLocal() as db:
            db.execute(delete(MeetingQARecord))
            db.execute(delete(MeetingSummary))
            db.execute(delete(TranscriptSegment))
            db.execute(delete(Meeting))
            db.execute(delete(User))
            db.add(
                User(
                    id=self.user_id,
                    username="qa-user",
                    email="qa-user@example.com",
                    password_salt="salt",
                    password_hash="hash",
                )
            )
            db.add(
                Meeting(
                    id=self.meeting_id,
                    user_id=self.user_id,
                    title="站会录音",
                    filename="daily.wav",
                    stored_filename="daily.wav",
                    audio_path=str((_TEST_DIR / "uploads" / "daily.wav").resolve()),
                    content_type="audio/wav",
                    duration_label="00:30",
                    language="zh",
                    status="transcribed",
                    transcript_text="张三负责上线准备，李四负责整理风险清单，下周一之前需要完成确认。",
                )
            )
            db.add_all(
                [
                    TranscriptSegment(meeting_id=self.meeting_id, start=0.0, end=8.0, text="张三负责上线准备。"),
                    TranscriptSegment(meeting_id=self.meeting_id, start=8.0, end=18.0, text="李四负责整理风险清单。"),
                    TranscriptSegment(meeting_id=self.meeting_id, start=18.0, end=28.0, text="下周一之前需要完成确认。"),
                ]
            )
            db.commit()

        _SESSIONS[self.token] = UserProfile(id=self.user_id, username="qa-user", email="qa-user@example.com")

    def test_can_ask_question_for_transcribed_meeting(self):
        response = self.client.post(
            f"/api/meetings/{self.meeting_id}/ask",
            json={"question": "谁负责整理风险清单？"},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["answer"])
        self.assertGreaterEqual(len(body["citations"]), 1)
        first_citation = body["citations"][0]
        self.assertGreaterEqual(first_citation["start"], 0.0)
        self.assertGreaterEqual(first_citation["end"], first_citation["start"])

        detail = self.client.get(
            f"/api/meetings/{self.meeting_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(detail.status_code, 200)
        detail_body = detail.json()
        self.assertEqual(len(detail_body["qa_records"]), 1)
        self.assertEqual(detail_body["qa_records"][0]["question"], "谁负责整理风险清单？")

    def test_rejects_question_for_untranscribed_meeting(self):
        with SessionLocal() as db:
            meeting = db.get(Meeting, self.meeting_id)
            meeting.transcript_text = ""
            db.execute(delete(TranscriptSegment).where(TranscriptSegment.meeting_id == self.meeting_id))
            db.commit()

        response = self.client.post(
            f"/api/meetings/{self.meeting_id}/ask",
            json={"question": "现在能问吗？"},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("尚未完成转录", response.json()["detail"])

    def test_rejects_empty_question(self):
        response = self.client.post(
            f"/api/meetings/{self.meeting_id}/ask",
            json={"question": ""},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
