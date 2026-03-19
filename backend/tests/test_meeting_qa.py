import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

_TEST_DIR = Path(tempfile.mkdtemp(prefix="asr-qa-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'meeting_qa_test.db'}"
os.environ["UPLOAD_DIR"] = str(_TEST_DIR / "uploads")
os.environ["SMTP_HOST"] = "smtp.example.com"
os.environ["SMTP_PORT"] = "587"
os.environ["SMTP_USERNAME"] = "mailer"
os.environ["SMTP_PASSWORD"] = "secret"
os.environ["SMTP_FROM_EMAIL"] = "no-reply@example.com"
os.environ["SMTP_FROM_NAME"] = "Audio Memo"
os.environ["SMTP_USE_TLS"] = "false"
os.environ["SUMMARY_EMAIL_AUTO_SEND"] = "false"
os.environ["AI_RUNTIME_ENABLED"] = "false"
os.environ["SUMMARY_ENGINE"] = "legacy"
os.environ["QA_ENGINE"] = "legacy"

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import Meeting, MeetingQARecord, MeetingSummary, MeetingSummaryEmailDelivery, TranscriptSegment, User
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingSummaryResponse, TranscriptJobStatusResponse
from app.services.auth_service import _SESSIONS
from app.services.email_service import settings as email_settings
from app.services.minimax_service import settings as minimax_settings
from app.services.transcription_service import _job_cancel_flags, _meeting_job_index, _store_job, _transcription_jobs


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
        _transcription_jobs.clear()
        _job_cancel_flags.clear()
        _meeting_job_index.clear()
        (_TEST_DIR / "uploads").mkdir(parents=True, exist_ok=True)
        ((_TEST_DIR / "uploads") / "daily.wav").write_bytes(b"audio")

        with SessionLocal() as db:
            db.execute(delete(MeetingQARecord))
            db.execute(delete(MeetingSummaryEmailDelivery))
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
            db.commit()
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
            db.add(
                MeetingSummary(
                    meeting_id=self.meeting_id,
                    summary="本次会议明确了上线准备、风险清单整理和最终确认时间。",
                    keywords_json='["上线准备", "风险清单", "确认时间"]',
                    todos_json='["张三完成上线准备", "李四整理风险清单", "下周一前完成确认"]',
                )
            )
            db.commit()

        _SESSIONS[self.token] = UserProfile(id=self.user_id, username="qa-user", email="qa-user@example.com")
        email_settings.summary_email_auto_send = False
        minimax_settings.summary_email_auto_send = False

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

    def test_rejects_question_for_stopped_meeting(self):
        with SessionLocal() as db:
            meeting = db.get(Meeting, self.meeting_id)
            meeting.status = "stopped"
            db.commit()

        response = self.client.post(
            f"/api/meetings/{self.meeting_id}/ask",
            json={"question": "谁负责整理风险清单？"},
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

    def test_can_send_summary_email_manually(self):
        with patch("app.services.email_service._send_message") as mock_send:
            response = self.client.post(
                f"/api/meetings/{self.meeting_id}/send-summary-email",
                headers={"Authorization": f"Bearer {self.token}"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "sent")
        self.assertEqual(body["recipient_email"], "qa-user@example.com")
        self.assertTrue(body["sent_at"])
        mock_send.assert_called_once()

        detail = self.client.get(
            f"/api/meetings/{self.meeting_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(detail.status_code, 200)
        status_body = detail.json()["summary_email"]
        self.assertTrue(status_body["enabled"])
        self.assertEqual(status_body["last_status"], "sent")
        self.assertEqual(status_body["last_delivery_type"], "manual")
        self.assertEqual(status_body["recipient_email"], "qa-user@example.com")

    def test_manual_email_requires_authentication(self):
        response = self.client.post(f"/api/meetings/{self.meeting_id}/send-summary-email")
        self.assertEqual(response.status_code, 401)

    def test_manual_email_rejects_non_owner(self):
        outsider_token = "outsider-token"
        with SessionLocal() as db:
            db.add(
                User(
                    id=202,
                    username="outsider",
                    email="outsider@example.com",
                    password_salt="salt",
                    password_hash="hash",
                )
            )
            db.commit()

        _SESSIONS[outsider_token] = UserProfile(id=202, username="outsider", email="outsider@example.com")
        response = self.client.post(
            f"/api/meetings/{self.meeting_id}/send-summary-email",
            headers={"Authorization": f"Bearer {outsider_token}"},
        )

        self.assertEqual(response.status_code, 404)

    def test_manual_email_requires_existing_summary(self):
        with SessionLocal() as db:
            db.execute(delete(MeetingSummary).where(MeetingSummary.meeting_id == self.meeting_id))
            db.commit()

        response = self.client.post(
            f"/api/meetings/{self.meeting_id}/send-summary-email",
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("请先生成会议摘要", response.json()["detail"])

    def test_manual_email_returns_503_when_smtp_not_configured(self):
        original_host = email_settings.smtp_host
        email_settings.smtp_host = ""
        try:
            response = self.client.post(
                f"/api/meetings/{self.meeting_id}/send-summary-email",
                headers={"Authorization": f"Bearer {self.token}"},
            )
        finally:
            email_settings.smtp_host = original_host

        self.assertEqual(response.status_code, 503)

        detail = self.client.get(
            f"/api/meetings/{self.meeting_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(detail.status_code, 200)
        status_body = detail.json()["summary_email"]
        self.assertEqual(status_body["last_status"], "failed")
        self.assertEqual(status_body["last_delivery_type"], "manual")
        self.assertIn("SMTP", status_body["last_error"])

    def test_summary_generation_can_auto_send_email(self):
        minimax_settings.summary_email_auto_send = True
        email_settings.summary_email_auto_send = True

        with patch(
            "app.services.minimax_service.build_summary_with_graph",
            new=AsyncMock(
                return_value=MeetingSummaryResponse(
                    summary="自动生成的会议摘要",
                    keywords=["自动发送", "摘要"],
                    todos=["发送邮件"],
                )
            ),
        ), patch("app.services.email_service._send_message") as mock_send:
            response = self.client.post(
                "/api/summary",
                json={"meeting_id": self.meeting_id},
                headers={"Authorization": f"Bearer {self.token}"},
            )

        self.assertEqual(response.status_code, 200)
        mock_send.assert_called_once()

        detail = self.client.get(
            f"/api/meetings/{self.meeting_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(detail.status_code, 200)
        status_body = detail.json()["summary_email"]
        self.assertEqual(status_body["last_status"], "sent")
        self.assertEqual(status_body["last_delivery_type"], "auto")

    def test_auto_send_failure_does_not_break_summary_generation(self):
        minimax_settings.summary_email_auto_send = True
        email_settings.summary_email_auto_send = True

        with patch(
            "app.services.minimax_service.build_summary_with_graph",
            new=AsyncMock(
                return_value=MeetingSummaryResponse(
                    summary="自动生成的会议摘要",
                    keywords=["失败回退"],
                    todos=["记录失败"],
                )
            ),
        ), patch("app.services.email_service._send_message", side_effect=RuntimeError("smtp down")):
            response = self.client.post(
                "/api/summary",
                json={"meeting_id": self.meeting_id},
                headers={"Authorization": f"Bearer {self.token}"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"], "自动生成的会议摘要")

        detail = self.client.get(
            f"/api/meetings/{self.meeting_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(detail.status_code, 200)
        status_body = detail.json()["summary_email"]
        self.assertEqual(status_body["last_status"], "failed")
        self.assertEqual(status_body["last_delivery_type"], "auto")
        self.assertIn("smtp down", status_body["last_error"])

    def test_meeting_detail_includes_active_transcription_job(self):
        _store_job(
            TranscriptJobStatusResponse(
                job_id="job-201",
                status="processing",
                meeting_id=self.meeting_id,
                filename="daily.wav",
                language="zh",
                text="张三负责上线准备。",
                segments=[{"start": 0.0, "end": 8.0, "text": "张三负责上线准备。"}],
                total_chunks=3,
                completed_chunks=1,
                error=None,
            )
        )
        with SessionLocal() as db:
            meeting = db.get(Meeting, self.meeting_id)
            meeting.status = "transcribing"
            meeting.transcript_text = "张三负责上线准备。"
            db.commit()

        response = self.client.get(
            f"/api/meetings/{self.meeting_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "transcribing")
        self.assertEqual(body["transcription_job"]["status"], "processing")
        self.assertEqual(body["transcription_job"]["completed_chunks"], 1)
        self.assertTrue(body["transcription_job"]["is_stoppable"])

    def test_can_delete_single_meeting(self):
        response = self.client.delete(
            f"/api/meetings/{self.meeting_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_id"], self.meeting_id)

        with SessionLocal() as db:
            self.assertIsNone(db.get(Meeting, self.meeting_id))
            self.assertEqual(db.query(TranscriptSegment).count(), 0)
            self.assertEqual(db.query(MeetingSummary).count(), 0)
            self.assertEqual(db.query(MeetingQARecord).count(), 0)

        self.assertFalse(((_TEST_DIR / "uploads") / "daily.wav").exists())

    def test_can_clear_all_meetings(self):
        with SessionLocal() as db:
            db.add(
                Meeting(
                    id=202,
                    user_id=self.user_id,
                    title="复盘录音",
                    filename="retro.wav",
                    stored_filename="retro.wav",
                    audio_path=str((_TEST_DIR / "uploads" / "retro.wav").resolve()),
                    content_type="audio/wav",
                    duration_label="00:10",
                    language="zh",
                    status="draft",
                    transcript_text="",
                )
            )
            db.commit()
        ((_TEST_DIR / "uploads") / "retro.wav").write_bytes(b"audio")

        response = self.client.delete(
            "/api/meetings",
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_count"], 2)

        with SessionLocal() as db:
            self.assertEqual(db.query(Meeting).count(), 0)


if __name__ == "__main__":
    unittest.main()
