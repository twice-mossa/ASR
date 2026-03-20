import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.schemas.meeting import TranscriptResponse, TranscriptSegment
from app.services.transcription_service import (
    TranscriptJobStatusResponse,
    _TranscriptionStopped,
    _job_cancel_flags,
    _meeting_job_index,
    _run_transcription_job,
    _send_groq_request_with_retry,
    _store_job,
    _transcription_jobs,
    stop_transcription_jobs_for_meeting,
)


class TranscriptionJobOrderingTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _transcription_jobs.clear()
        _job_cancel_flags.clear()
        _meeting_job_index.clear()

    async def test_meeting_job_marks_completed_after_persisting_transcript(self):
        job_id = "job-ordering"
        transcript = TranscriptResponse(
            filename="demo.wav",
            language="zh",
            text="这是转录结果",
            segments=[TranscriptSegment(start=0.0, end=1.0, text="这是转录结果")],
        )

        _store_job(
            TranscriptJobStatusResponse(
                job_id=job_id,
                status="queued",
                meeting_id=123,
                filename="demo.wav",
                language="zh",
                text="",
                segments=[],
                total_chunks=1,
                completed_chunks=0,
                error=None,
            )
        )

        def fake_save(meeting_id, result):
            self.assertEqual(meeting_id, 123)
            self.assertEqual(result.text, "这是转录结果")
            self.assertNotEqual(_transcription_jobs[job_id].status, "completed")

        with patch(
            "app.services.transcription_service._transcribe_from_bytes",
            new=AsyncMock(return_value=transcript),
        ), patch("app.services.transcription_service.save_transcript_result", side_effect=fake_save):
            await _run_transcription_job(job_id, "demo.wav", b"audio", "audio/wav", meeting_id=123)

        self.assertEqual(_transcription_jobs[job_id].status, "completed")
        self.assertEqual(_transcription_jobs[job_id].text, "这是转录结果")

    async def test_meeting_job_persists_partial_transcript_before_completion(self):
        job_id = "job-partial"
        partial = TranscriptResponse(
            filename="demo.wav",
            language="zh",
            text="第一段结果",
            segments=[TranscriptSegment(start=0.0, end=1.0, text="第一段结果")],
        )
        final = TranscriptResponse(
            filename="demo.wav",
            language="zh",
            text="第一段结果 第二段结果",
            segments=[
                TranscriptSegment(start=0.0, end=1.0, text="第一段结果"),
                TranscriptSegment(start=1.0, end=2.0, text="第二段结果"),
            ],
        )

        _store_job(
            TranscriptJobStatusResponse(
                job_id=job_id,
                status="queued",
                meeting_id=456,
                filename="demo.wav",
                language="zh",
                text="",
                segments=[],
                total_chunks=1,
                completed_chunks=0,
                error=None,
            )
        )

        partial_calls = []

        async def fake_transcribe(**kwargs):
            kwargs["on_partial"](partial, 1, 2)
            return final

        def fake_save_partial(meeting_id, result, status_value="transcribing"):
            partial_calls.append((meeting_id, result.text, status_value, _transcription_jobs[job_id].status))

        with patch(
            "app.services.transcription_service._transcribe_from_bytes",
            new=AsyncMock(side_effect=fake_transcribe),
        ), patch(
            "app.services.transcription_service.save_partial_transcript_result",
            side_effect=fake_save_partial,
        ), patch("app.services.transcription_service.save_transcript_result"):
            await _run_transcription_job(job_id, "demo.wav", b"audio", "audio/wav", meeting_id=456)

        self.assertEqual(partial_calls, [(456, "第一段结果", "transcribing", "processing")])
        self.assertEqual(_transcription_jobs[job_id].status, "completed")
        self.assertEqual(_transcription_jobs[job_id].completed_chunks, 1)
        self.assertEqual(_transcription_jobs[job_id].total_chunks, 2)

    async def test_groq_request_retries_then_returns_response(self):
        responses = [
            OSError("EOF occurred in violation of protocol (_ssl.c:997)"),
            OSError("temporary"),
            SimpleNamespace(status_code=200),
        ]

        def fake_request():
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with patch("app.services.transcription_service.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = await _send_groq_request_with_retry(filename="demo.wav", request_factory=fake_request)

        self.assertIsNotNone(result)
        self.assertEqual(sleep_mock.await_count, 2)

    async def test_groq_request_raises_friendly_error_after_retries(self):
        def fake_request():
            raise OSError("EOF occurred in violation of protocol (_ssl.c:997)")

        with patch("app.services.transcription_service.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            with self.assertRaises(HTTPException) as ctx:
                await _send_groq_request_with_retry(filename="demo.wav", request_factory=fake_request)

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail, "远程转录服务网络异常，请稍后重试。")
        self.assertEqual(sleep_mock.await_count, 2)

    async def test_meeting_job_marks_stopped_after_stop_request(self):
        job_id = "job-stop"
        partial = TranscriptResponse(
            filename="demo.wav",
            language="zh",
            text="第一段结果",
            segments=[TranscriptSegment(start=0.0, end=1.0, text="第一段结果")],
        )

        _store_job(
            TranscriptJobStatusResponse(
                job_id=job_id,
                status="queued",
                meeting_id=999,
                filename="demo.wav",
                language="zh",
                text="",
                segments=[],
                total_chunks=2,
                completed_chunks=0,
                error=None,
            )
        )

        async def fake_transcribe(**kwargs):
            kwargs["on_partial"](partial, 1, 2)
            raise _TranscriptionStopped()

        with patch(
            "app.services.transcription_service._transcribe_from_bytes",
            new=AsyncMock(side_effect=fake_transcribe),
        ), patch("app.services.transcription_service.save_partial_transcript_result"), patch(
            "app.services.transcription_service.update_meeting_status"
        ) as update_status:
            stop_transcription_jobs_for_meeting(999)
            await _run_transcription_job(job_id, "demo.wav", b"audio", "audio/wav", meeting_id=999)

        self.assertEqual(_transcription_jobs[job_id].status, "stopped")
        update_status.assert_called_with(999, status_value="stopped", error_message="")


if __name__ == "__main__":
    unittest.main()
