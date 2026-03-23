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
    is_stoppable: bool = False
    partial_available: bool = False
    error: str | None = None


class SummaryRequest(BaseModel):
    meeting_id: int | None = None
    transcribed_text: str = ""


class MeetingSummaryResponse(BaseModel):
    summary: str
    keywords: list[str]
    todos: list[str]


class MeetingSummaryEmailStatusResponse(BaseModel):
    enabled: bool
    recipient_email: str = ""
    last_status: str = "idle"
    last_delivery_type: str | None = None
    last_sent_at: str | None = None
    last_error: str | None = None


class MeetingSummaryEmailSendResponse(BaseModel):
    message: str
    recipient_email: str
    status: str
    sent_at: str | None = None


class MeetingCitation(BaseModel):
    text: str
    start: float
    end: float
    segment_id: int | None = None


class MeetingEvidenceBlock(BaseModel):
    title: str
    start: float
    end: float
    summary: str
    citations: list[MeetingCitation] = Field(default_factory=list)


class MeetingAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class MeetingAskResponse(BaseModel):
    answer: str
    citations: list[MeetingCitation] = Field(default_factory=list)
    reasoning_summary: str | None = None
    answer_type: str | None = None
    topic_labels: list[str] = Field(default_factory=list)
    evidence_blocks: list[MeetingEvidenceBlock] = Field(default_factory=list)


class MeetingQARecordResponse(BaseModel):
    id: int
    question: str
    answer: str
    citations: list[MeetingCitation] = Field(default_factory=list)
    reasoning_summary: str | None = None
    answer_type: str | None = None
    topic_labels: list[str] = Field(default_factory=list)
    evidence_blocks: list[MeetingEvidenceBlock] = Field(default_factory=list)
    created_at: str


class MeetingCreateRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    duration_label: str = Field(default="--:--", max_length=32)


class MeetingUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


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
    transcription_job: TranscriptJobStatusResponse | None = None
    summary: MeetingSummaryResponse | None = None
    summary_email: MeetingSummaryEmailStatusResponse
    qa_records: list[MeetingQARecordResponse] = Field(default_factory=list)
    knowledge_status: str = "idle"
