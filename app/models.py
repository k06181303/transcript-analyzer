from pydantic import BaseModel, Field
from typing import List, Optional


class MeetingTranscript(BaseModel):
    text: str = Field(..., description="逐字稿原文")
    duration: Optional[float] = Field(None, description="音檔時間長度（秒）")
    language: str = Field(default="zh", description="逐字稿語言")
    confidence: Optional[float] = Field(None, description="轉錄信心分數（0–100）")


class MeetingSummary(BaseModel):
    summary: str = Field(..., description="整體摘要")
    key_points: List[str] = Field(default_factory=list, description="重點整理清單")
    participants: List[str] = Field(default_factory=list, description="發言者名單（若有）")
    keywords: List[str] = Field(default_factory=list, description="關鍵詞列表")


class TranscribeResponse(BaseModel):
    transcript: MeetingTranscript
    summary: MeetingSummary
