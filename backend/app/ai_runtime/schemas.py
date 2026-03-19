from __future__ import annotations

from pydantic import BaseModel, Field


class SummaryStructuredOutput(BaseModel):
    summary: str = Field(default="")
    keywords: list[str] = Field(default_factory=list)
    todos: list[str] = Field(default_factory=list)


class CitedAnswerStructuredOutput(BaseModel):
    answer: str = Field(default="")
    reasoning_summary: str = Field(default="")
    citation_segment_ids: list[int] = Field(default_factory=list)


class QuestionIntent(BaseModel):
    question_type: str = Field(default="fact")
    rewritten_question: str = Field(default="")
    entities: list[str] = Field(default_factory=list)
    anchors: list[str] = Field(default_factory=list)
    use_recent_history: bool = Field(default=False)


class RetrievalCandidate(BaseModel):
    segment_id: int
    score: float = Field(default=0.0)
    source: str = Field(default="")
    reason: str = Field(default="")


class EvidenceWindow(BaseModel):
    window_id: int
    segment_ids: list[int] = Field(default_factory=list)
    start: float = Field(default=0.0)
    end: float = Field(default=0.0)
    text: str = Field(default="")
    score: float = Field(default=0.0)


class RerankedEvidenceWindows(BaseModel):
    ordered_window_ids: list[int] = Field(default_factory=list)
    reasoning_summary: str = Field(default="")


class GroundedAnswerStructuredOutput(BaseModel):
    answer: str = Field(default="")
    reasoning_summary: str = Field(default="")
    citation_window_ids: list[int] = Field(default_factory=list)


class GroundedAnswerCheck(BaseModel):
    grounded: bool = Field(default=True)
    answer: str = Field(default="")
    reasoning_summary: str = Field(default="")
    citation_window_ids: list[int] = Field(default_factory=list)
    insufficiency_reason: str = Field(default="")
