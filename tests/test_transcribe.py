"""
測試 summarize_transcript 功能（使用 sample_transcript.txt，不呼叫 Whisper API）
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# 讓 pytest 找到 app 套件
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import MeetingSummary, MeetingTranscript
from app.summarize import summarize_transcript
from app.transcribe import transcribe_audio

SAMPLE_PATH = Path(__file__).parent.parent / "sample" / "sample_transcript.txt"


@pytest.fixture
def sample_transcript() -> MeetingTranscript:
    text = SAMPLE_PATH.read_text(encoding="utf-8")
    return MeetingTranscript(text=text, language="zh")


# ---------------------------------------------------------------------------
# 跳過條件：沒有設定 ANTHROPIC_API_KEY 時跳過（CI 環境保護）
# ---------------------------------------------------------------------------
skip_if_no_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY 未設定，跳過需要 API 的測試",
)


@skip_if_no_key
def test_summarize_returns_meeting_summary(sample_transcript):
    """summarize_transcript 應回傳 MeetingSummary 物件"""
    result = summarize_transcript(sample_transcript)
    assert isinstance(result, MeetingSummary)


@skip_if_no_key
def test_summary_has_content(sample_transcript):
    """summary 欄位不應為空"""
    result = summarize_transcript(sample_transcript)
    assert result.summary, "summary 不應為空字串"
    assert len(result.summary) > 10


@skip_if_no_key
def test_key_points_is_list(sample_transcript):
    """key_points 應為 list 且有內容"""
    result = summarize_transcript(sample_transcript)
    assert isinstance(result.key_points, list)
    assert len(result.key_points) > 0, "應有至少一個重點"


@skip_if_no_key
def test_participants_detected(sample_transcript):
    """應能辨識出參與者"""
    result = summarize_transcript(sample_transcript)
    assert isinstance(result.participants, list)
    assert len(result.participants) > 0, "應辨識出至少一位參與者"


@skip_if_no_key
def test_keywords_is_list(sample_transcript):
    """keywords 應為 list 且有內容"""
    result = summarize_transcript(sample_transcript)
    assert isinstance(result.keywords, list)
    assert len(result.keywords) >= 3, "應有至少 3 個關鍵詞"


# ---------------------------------------------------------------------------
# 不需要 API key 的單元測試
# ---------------------------------------------------------------------------
def test_sample_file_exists():
    """sample_transcript.txt 必須存在"""
    assert SAMPLE_PATH.exists(), f"找不到範例檔案：{SAMPLE_PATH}"


def test_sample_file_not_empty():
    """sample_transcript.txt 不可為空"""
    content = SAMPLE_PATH.read_text(encoding="utf-8")
    assert len(content) > 100, "範例逐字稿過短"


def test_meeting_transcript_model():
    """MeetingTranscript 基本驗證"""
    t = MeetingTranscript(text="測試文字", language="zh")
    assert t.text == "測試文字"
    assert t.language == "zh"
    assert t.duration is None


def test_meeting_summary_model():
    """MeetingSummary 預設值驗證"""
    s = MeetingSummary(summary="這是摘要")
    assert s.summary == "這是摘要"
    assert s.key_points == []
    assert s.participants == []
    assert s.keywords == []


def test_transcribe_audio_reads_txt():
    """transcribe_audio 應能直接讀取 .txt 檔，不需要 API key"""
    result = transcribe_audio(str(SAMPLE_PATH))
    assert isinstance(result, MeetingTranscript)
    assert len(result.text) > 100
    assert result.language == "zh"


def test_transcribe_audio_file_not_found():
    """transcribe_audio 對不存在的檔案應拋出 FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        transcribe_audio("nonexistent_file.txt")


def test_transcribe_audio_unsupported_format(tmp_path):
    """transcribe_audio 對不支援的格式應拋出 ValueError"""
    fake_file = tmp_path / "audio.xyz"
    fake_file.write_text("content")
    with pytest.raises(ValueError, match="不支援的格式"):
        transcribe_audio(str(fake_file))
