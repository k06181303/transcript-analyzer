"""
LLM-as-judge 評估器
對 summarize_transcript 的輸出品質自動打分，指標：
  - completeness   完整度  0-5
  - accuracy       準確性  0-5
  - format_ok      格式正確率  0 or 1
  - coverage_rate  key_points 涵蓋率  0.0-1.0
"""

import os
from pathlib import Path

import anthropic
import instructor
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 評分結果 schema
# ---------------------------------------------------------------------------

class EvalScore(BaseModel):
    completeness: int = Field(..., ge=0, le=5, description="摘要完整度（0-5）")
    accuracy: int = Field(..., ge=0, le=5, description="內容準確性（0-5）")
    format_ok: int = Field(..., ge=0, le=1, description="格式是否正確（0 or 1）")
    coverage_rate: float = Field(..., ge=0.0, le=1.0, description="key_points 涵蓋率（0.0-1.0）")
    reasoning: str = Field(..., description="評分理由（簡短說明）")


JUDGE_SYSTEM_PROMPT = """你是一位嚴格但公正的 AI 輸出品質評審，請根據「標準答案」評估「模型輸出」的品質。

評分標準：
- completeness（完整度 0-5）：模型輸出的摘要涵蓋了多少原文的重要資訊
  5=涵蓋所有重要資訊，4=涵蓋大部分，3=涵蓋一半，2=涵蓋少數，1=幾乎沒有，0=完全無關
- accuracy（準確性 0-5）：模型輸出的內容是否與原文事實一致，無捏造或扭曲
  5=完全正確，4=極少錯誤，3=部分正確，2=多處錯誤，1=大量錯誤，0=嚴重錯誤
- format_ok（格式正確率 0 or 1）：summary 是否為連貫文字、key_points 是否為列表且每項為完整句子
  1=格式正確，0=格式有問題
- coverage_rate（key_points 涵蓋率 0.0-1.0）：模型輸出的 key_points 與標準答案 key_points 的語意重疊比例
  1.0=完全涵蓋，0.5=涵蓋一半，0.0=完全未涵蓋

請輸出 JSON 格式的評分結果，不要加任何額外說明。"""


def evaluate(
    original_text: str,
    golden_summary: str,
    golden_key_points: list[str],
    model_summary: str,
    model_key_points: list[str],
) -> EvalScore:
    """
    用 Claude 評估模型輸出品質，回傳 EvalScore。

    Args:
        original_text: 原始逐字稿
        golden_summary: 人工標注的理想摘要
        golden_key_points: 人工標注的理想重點列表
        model_summary: 模型產出的摘要
        model_key_points: 模型產出的重點列表

    Returns:
        EvalScore 物件
    """
    try:
        anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    except KeyError:
        raise RuntimeError("缺少環境變數 ANTHROPIC_API_KEY")

    client = instructor.from_anthropic(anthropic_client)

    golden_kp_str = "\n".join(f"- {p}" for p in golden_key_points)
    model_kp_str = "\n".join(f"- {p}" for p in model_key_points)

    user_content = f"""## 原始逐字稿（前 500 字）
{original_text[:500]}

## 標準答案
### 理想摘要
{golden_summary}

### 理想重點
{golden_kp_str}

## 模型輸出
### 模型摘要
{model_summary}

### 模型重點
{model_kp_str}

請依照評分標準給出分數。"""

    return client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        response_model=EvalScore,
    )
