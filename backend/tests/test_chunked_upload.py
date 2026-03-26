import os
import tempfile
import unittest
from pathlib import Path

_TEST_DIR = Path(tempfile.mkdtemp(prefix="asr-chunk-upload-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'chunk_upload_test.db'}"
os.environ["UPLOAD_DIR"] = str(_TEST_DIR / "uploads")
os.environ["AI_RUNTIME_ENABLED"] = "false"

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import Base, SessionLocal, engine, init_database
from app.main import app
from app.models import Meeting, User
from app.schemas.auth import UserProfile
from app.services.auth_service import _SESSIONS


class ChunkedUploadTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_database()
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.token = "chunk-upload-token"
        self.user_id = 301
        _SESSIONS.clear()
        Path(os.environ["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

        with SessionLocal() as db:
            db.execute(delete(Meeting))
            db.execute(delete(User))
            db.add(
                User(
                    id=self.user_id,
                    username="chunk-user",
                    email="chunk-user@example.com",
                    password_salt="salt",
                    password_hash="hash",
                )
            )
            db.commit()

        _SESSIONS[self.token] = UserProfile(id=self.user_id, username="chunk-user", email="chunk-user@example.com")

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_chunked_upload_can_complete_after_out_of_order_parts(self):
        raw = b"abcde" * 1024 * 512
        chunk_size = len(raw) // 3
        total_chunks = (len(raw) + chunk_size - 1) // chunk_size

        init_response = self.client.post(
            "/api/uploads/init",
            json={
                "filename": "demo.wav",
                "duration_label": "12:34",
                "file_size": len(raw),
                "chunk_size": chunk_size,
                "total_chunks": total_chunks,
                "content_type": "audio/wav",
            },
            headers=self._auth_headers(),
        )
        self.assertEqual(init_response.status_code, 200)
        upload_id = init_response.json()["upload_id"]

        parts = [raw[index * chunk_size : min(len(raw), (index + 1) * chunk_size)] for index in range(total_chunks)]
        upload_order = [2, 1, 3] if total_chunks == 3 else list(range(total_chunks, 0, -1))
        for part_number in upload_order:
            response = self.client.put(
                f"/api/uploads/{upload_id}/parts/{part_number}",
                headers=self._auth_headers(),
                files={"file": (f"part-{part_number}.bin", parts[part_number - 1], "application/octet-stream")},
            )
            self.assertEqual(response.status_code, 200)

        complete_response = self.client.post(
            f"/api/uploads/{upload_id}/complete",
            headers=self._auth_headers(),
        )
        self.assertEqual(complete_response.status_code, 200)
        meeting = complete_response.json()
        self.assertEqual(meeting["filename"], "demo.wav")
        self.assertEqual(meeting["duration_label"], "12:34")

        with SessionLocal() as db:
            saved_meeting = db.get(Meeting, meeting["id"])
            self.assertIsNotNone(saved_meeting)
            self.assertEqual(Path(saved_meeting.audio_path).read_bytes(), raw)

    def test_chunked_upload_rejects_complete_when_part_missing(self):
        raw = b"0123456789" * 1000
        chunk_size = 4096
        total_chunks = (len(raw) + chunk_size - 1) // chunk_size

        init_response = self.client.post(
            "/api/uploads/init",
            json={
                "filename": "missing.wav",
                "duration_label": "--:--",
                "file_size": len(raw),
                "chunk_size": chunk_size,
                "total_chunks": total_chunks,
                "content_type": "audio/wav",
            },
            headers=self._auth_headers(),
        )
        self.assertEqual(init_response.status_code, 200)
        upload_id = init_response.json()["upload_id"]

        first_chunk = raw[:chunk_size]
        response = self.client.put(
            f"/api/uploads/{upload_id}/parts/1",
            headers=self._auth_headers(),
            files={"file": ("part-1.bin", first_chunk, "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 200)

        complete_response = self.client.post(
            f"/api/uploads/{upload_id}/complete",
            headers=self._auth_headers(),
        )
        self.assertEqual(complete_response.status_code, 400)
        self.assertIn("缺少分片", complete_response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
