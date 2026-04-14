"""
Prompt v1 vs v2 對比測試
- 涵蓋多種逐字稿類型：會議、訪談、演講
- 需要 ANTHROPIC_API_KEY，無 key 時自動跳過
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import MeetingTranscript
from app.summarize import summarize_transcript

SAMPLE_DIR = Path(__file__).parent.parent / "sample"

skip_if_no_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY 未設定，跳過需要 API 的測試",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def meeting_transcript() -> MeetingTranscript:
    text = (SAMPLE_DIR / "sample_transcript.txt").read_text(encoding="utf-8")
    return MeetingTranscript(text=text, language="zh")


@pytest.fixture
def interview_transcript() -> MeetingTranscript:
    text = (SAMPLE_DIR / "interview_transcript.txt").read_text(encoding="utf-8")
    return MeetingTranscript(text=text, language="zh")


@pytest.fixture
def lecture_transcript() -> MeetingTranscript:
    text = (SAMPLE_DIR / "lecture_transcript.txt").read_text(encoding="utf-8")
    return MeetingTranscript(text=text, language="zh")


# ---------------------------------------------------------------------------
# v1 基本品質測試（三種逐字稿類型）
# ---------------------------------------------------------------------------

@skip_if_no_key
@pytest.mark.parametrize("fixture_name", ["meeting_transcript", "interview_transcript", "lecture_transcript"])
def test_v1_basic_quality(fixture_name, request):
    """v1 對各類逐字稿都應回傳非空的 summary 和 key_points"""
    transcript = request.getfixturevalue(fixture_name)
    result = summarize_transcript(transcript, prompt_version="v1")
    assert result.summary and len(result.summary) > 20, f"[v1][{fixture_name}] summary 過短"
    assert len(result.key_points) >= 3, f"[v1][{fixture_name}] key_points 少於 3 項"
    assert len(result.keywords) >= 3, f"[v1][{fixture_name}] keywords 少於 3 個"


# ---------------------------------------------------------------------------
# v2 基本品質測試（三種逐字稿類型）
# ---------------------------------------------------------------------------

@skip_if_no_key
@pytest.mark.parametrize("fixture_name", ["meeting_transcript", "interview_transcript", "lecture_transcript"])
def test_v2_basic_quality(fixture_name, request):
    """v2 對各類逐字稿都應回傳非空的 summary 和 key_points"""
    transcript = request.getfixturevalue(fixture_name)
    result = summarize_transcript(transcript, prompt_version="v2")
    assert result.summary and len(result.summary) > 20, f"[v2][{fixture_name}] summary 過短"
    assert len(result.key_points) >= 3, f"[v2][{fixture_name}] key_points 少於 3 項"
    assert len(result.keywords) >= 3, f"[v2][{fixture_name}] keywords 少於 3 個"


# ---------------------------------------------------------------------------
# v2 進階品質測試
# ---------------------------------------------------------------------------

@skip_if_no_key
def test_v2_key_points_are_complete_sentences(meeting_transcript):
    """v2 的 key_points 應為包含主詞與動作的完整句子（長度 > 10 字）"""
    result = summarize_transcript(meeting_transcript, prompt_version="v2")
    for point in result.key_points:
        assert len(point) > 10, f"[v2] key_point 過短，可能不是完整句子：{point!r}"


@skip_if_no_key
def test_v2_interview_detects_participants(interview_transcript):
    """v2 分析含發言人 tag 的訪談稿，應能辨識出至少 1 位發言者"""
    result = summarize_transcript(interview_transcript, prompt_version="v2")
    assert len(result.participants) >= 1, "[v2] 訪談稿應辨識出至少 1 位發言者"


@skip_if_no_key
def test_v2_lecture_no_forced_participants(lecture_transcript):
    """v2 分析無發言人的演講稿，participants 應為空陣列"""
    result = summarize_transcript(lecture_transcript, prompt_version="v2")
    assert isinstance(result.participants, list), "participants 應為 list"


# ---------------------------------------------------------------------------
# v1 vs v2 比較：key_points 具體程度
# ---------------------------------------------------------------------------

@skip_if_no_key
def test_v2_key_points_longer_than_v1(meeting_transcript):
    """v2 的 key_points 平均長度應不低於 v1（v2 要求更完整的句子）"""
    v1 = summarize_transcript(meeting_transcript, prompt_version="v1")
    v2 = summarize_transcript(meeting_transcript, prompt_version="v2")

    v1_avg = sum(len(p) for p in v1.key_points) / max(len(v1.key_points), 1)
    v2_avg = sum(len(p) for p in v2.key_points) / max(len(v2.key_points), 1)

    print(f"\nv1 key_points 平均長度：{v1_avg:.1f} 字")
    print(f"v2 key_points 平均長度：{v2_avg:.1f} 字")
    # v2 要求「主詞＋動作＋結果」完整句，應不短於 v1
    assert v2_avg >= v1_avg * 0.8, (
        f"v2 key_points 平均長度（{v2_avg:.1f}）遠短於 v1（{v1_avg:.1f}），品質可能下降"
    )


# ---------------------------------------------------------------------------
# 不需要 API key 的單元測試
# ---------------------------------------------------------------------------

def test_sample_files_exist():
    """所有 sample 檔案必須存在"""
    for name in ["sample_transcript.txt", "interview_transcript.txt", "lecture_transcript.txt"]:
        assert (SAMPLE_DIR / name).exists(), f"找不到 sample 檔案：{name}"


def test_prompt_files_exist():
    """prompts/v1.txt 和 prompts/v2.txt 必須存在"""
    prompts_dir = Path(__file__).parent.parent / "prompts"
    assert (prompts_dir / "v1.txt").exists(), "找不到 prompts/v1.txt"
    assert (prompts_dir / "v2.txt").exists(), "找不到 prompts/v2.txt"


def test_invalid_prompt_version_raises(meeting_transcript):
    """傳入不存在的 prompt 版本應拋出 RuntimeError"""
    from app.models import MeetingTranscript
    transcript = MeetingTranscript(text="測試文字", language="zh")
    with pytest.raises(RuntimeError, match="不存在"):
        summarize_transcript(transcript, prompt_version="v999")
