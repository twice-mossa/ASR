from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: str


class TranscriptResponse(BaseModel):
    filename: str
    language: str = "zh"
    text: str
    segments: list[TranscriptSegment]


class TranscriptJobCreateResponse(BaseModel):
    job_id: str
    status: str


class TranscriptJobStatusResponse(BaseModel):
    job_id: str
    status: str
    filename: str = ""
    language: str = "zh"
    text: str = ""
    segments: list[TranscriptSegment] = Field(default_factory=list)
    total_chunks: int = 1
    completed_chunks: int = 0
    error: str | None = None


class SummaryRequest(BaseModel):
    transcribed_text: str


class MeetingSummaryResponse(BaseModel):
    summary: str
    keywords: list[str]
    todos: list[str]
