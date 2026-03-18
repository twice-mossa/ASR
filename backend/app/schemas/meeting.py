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
    meeting_id: int | None = None


class TranscriptJobStatusResponse(BaseModel):
    job_id: str
    status: str
    meeting_id: int | None = None
    filename: str = ""
    language: str = "zh"
    text: str = ""
    segments: list[TranscriptSegment] = Field(default_factory=list)
    total_chunks: int = 1
    completed_chunks: int = 0
    error: str | None = None


class SummaryRequest(BaseModel):
    meeting_id: int | None = None
    transcribed_text: str = ""


class MeetingSummaryResponse(BaseModel):
    summary: str
    keywords: list[str]
    todos: list[str]


class MeetingCreateRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    duration_label: str = Field(default="--:--", max_length=32)


class MeetingListItem(BaseModel):
    id: int
    title: str
    filename: str
    duration_label: str
    language: str
    status: str
    preview: str
    created_at: str
    updated_at: str
    has_summary: bool


class MeetingDetailResponse(BaseModel):
    id: int
    title: str
    filename: str
    duration_label: str
    language: str
    status: str
    audio_url: str
    created_at: str
    updated_at: str
    error: str | None = None
    transcript: TranscriptResponse | None = None
    summary: MeetingSummaryResponse | None = None
