import logging
import os
import re
from pathlib import Path

import anthropic
import instructor
import tiktoken

from app.models import MeetingSummary, MeetingTranscript

logger = logging.getLogger(__name__)

TOKEN_CHUNK_SIZE = 1500  # 每段最多 token 數
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(version: str = "v1") -> str:
    """從 prompts/ 資料夾載入指定版本的 system prompt。"""
    path = PROMPTS_DIR / f"{version}.txt"
    if not path.exists():
        raise RuntimeError(f"Prompt 版本 '{version}' 不存在：{path}")
    return path.read_text(encoding="utf-8").strip()


def _split_by_tokens(text: str) -> list[str]:
    """用 tiktoken 計算 token 數，超過上限自動切段。"""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = []
    for i in range(0, len(tokens), TOKEN_CHUNK_SIZE):
        chunk_tokens = tokens[i : i + TOKEN_CHUNK_SIZE]
        chunks.append(enc.decode(chunk_tokens))
    return chunks


def _build_confidence_note(confidence: float | None) -> str:
    """根據 Whisper 信心分數產生 prompt 補充說明。"""
    if confidence is None:
        return ""
    if confidence >= 75:
        return ""  # 高品質，不需要特別提示
    if confidence >= 40:
        return (
            "\n\n【轉錄品質提示】此逐字稿由語音辨識自動產生，準確率中等（約 "
            f"{confidence:.0f}%）。部分詞彙可能有誤，請根據上下文語意推斷正確含意，"
            "不要直接引用疑似辨識錯誤的專有名詞。"
        )
    return (
        "\n\n【轉錄品質提示】此逐字稿由語音辨識自動產生，準確率較低（約 "
        f"{confidence:.0f}%）。請聚焦在整體語意與主題，避免引用細節數字或專有名詞，"
        "遇到不合理的詞彙請根據上下文自行修正理解。"
    )


def _analyze_structure(text: str) -> str:
    """
    純文字分析逐字稿結構特徵，產生動態備註注入 user message。
    不呼叫任何 API，完全免費。
    """
    notes = []

    # 發言者模式
    speaker_patterns = re.findall(r'[\[【]?[\w\s]{1,10}[\]】]?\s*[:：]', text)
    unique_speakers = {p.strip('[]【】 :：').strip() for p in speaker_patterns}
    unique_speakers = {s for s in unique_speakers if 1 < len(s) <= 8}
    if len(unique_speakers) >= 3:
        notes.append(f"多人對話（偵測到 {len(unique_speakers)} 位發言者），請特別標注各人重點")
    elif len(unique_speakers) == 2:
        notes.append("雙人對話，請標注雙方立場或觀點差異")
    elif len(unique_speakers) == 1:
        notes.append("單一發言者，聚焦主旨與論點脈絡")

    # 時間戳
    if re.search(r'\d{1,2}:\d{2}', text):
        notes.append("含時間戳，可依時序整理重點")

    # 問答結構
    question_count = text.count('？') + text.count('?')
    if question_count >= 5:
        notes.append(f"問答密集（約 {question_count} 個問句），請涵蓋關鍵問題與回答")

    # 領域偵測
    tech_kw = ['API', 'bug', '部署', '架構', '資料庫', '前端', '後端', '演算法', 'token', 'model', '模型', '訓練']
    biz_kw = ['營收', '客戶', '業績', '市場', '預算', '成本', '策略', '行銷', 'KPI', '季度']
    academic_kw = ['研究', '論文', '實驗', '假設', '數據', '分析', '文獻', '方法論']

    tech_hits = sum(1 for kw in tech_kw if kw in text)
    biz_hits = sum(1 for kw in biz_kw if kw in text)
    academic_hits = sum(1 for kw in academic_kw if kw in text)

    domain_max = max(tech_hits, biz_hits, academic_hits)
    if domain_max >= 3:
        if domain_max == tech_hits:
            notes.append("技術領域內容，請保留專業術語原文")
        elif domain_max == biz_hits:
            notes.append("商業/管理領域內容，請標注數字指標與決策")
        else:
            notes.append("學術/研究領域內容，請標注研究方法與結論")

    # 逐字稿長度
    char_count = len(text)
    if char_count > 5000:
        notes.append(f"長篇逐字稿（{char_count:,} 字元），確保涵蓋各段落主題，不遺漏後半部")

    if not notes:
        return ""

    return "\n\n[逐字稿特徵分析：" + "；".join(notes) + "]"


def _call_llm(client, text: str, system_prompt: str, structure_note: str = "") -> MeetingSummary:
    """呼叫 Claude Haiku，透過 instructor 強制回傳 MeetingSummary。"""
    user_content = f"以下是逐字稿：{structure_note}\n\n{text}"
    return client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
        response_model=MeetingSummary,
    )


def _merge_summaries(parts: list[MeetingSummary]) -> MeetingSummary:
    """將多段分析結果合併為一份摘要。"""
    if len(parts) == 1:
        return parts[0]

    combined_summary = "\n\n".join(
        f"【第{i+1}段摘要】{p.summary}" for i, p in enumerate(parts)
    )
    key_points: list[str] = []
    participants: set[str] = set()
    keywords: set[str] = set()

    for p in parts:
        key_points.extend(p.key_points)
        participants.update(p.participants)
        keywords.update(p.keywords)

    return MeetingSummary(
        summary=combined_summary,
        key_points=list(dict.fromkeys(key_points)),  # 保序去重
        participants=sorted(participants),
        keywords=sorted(keywords)[:10],
    )


def summarize_transcript(
    transcript: MeetingTranscript, prompt_version: str = "v3"
) -> MeetingSummary:
    """
    使用 Claude Haiku + instructor 將逐字稿摘要為結構化 MeetingSummary。
    以 tiktoken 計算 token 數，超過上限自動分段後合併。

    Args:
        transcript: MeetingTranscript 物件
        prompt_version: 使用的 prompt 版本（對應 prompts/<version>.txt）

    Returns:
        MeetingSummary 物件

    Raises:
        RuntimeError: API 呼叫失敗或 prompt 版本不存在
    """
    try:
        anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    except KeyError:
        raise RuntimeError("缺少環境變數 ANTHROPIC_API_KEY，請確認 .env 已設定。")

    client = instructor.from_anthropic(anthropic_client)
    base_prompt = _load_prompt(prompt_version)
    system_prompt = base_prompt + _build_confidence_note(transcript.confidence)
    text = transcript.text
    structure_note = _analyze_structure(text)

    enc = tiktoken.get_encoding("cl100k_base")
    token_count = len(enc.encode(text))

    if token_count <= TOKEN_CHUNK_SIZE:
        chunks = [text]
    else:
        logger.info(
            "逐字稿超過 %d tokens（共 %d tokens），進行分段處理",
            TOKEN_CHUNK_SIZE,
            token_count,
        )
        chunks = _split_by_tokens(text)

    logger.info("開始摘要（prompt=%s），共 %d 段", prompt_version, len(chunks))

    parts: list[MeetingSummary] = []
    for idx, chunk in enumerate(chunks, start=1):
        logger.info("處理第 %d/%d 段...", idx, len(chunks))
        try:
            result = _call_llm(client, chunk, system_prompt, structure_note)
            parts.append(result)
        except Exception as exc:
            logger.exception("第 %d 段摘要失敗", idx)
            raise RuntimeError(f"第 {idx} 段摘要失敗：{exc}") from exc

    merged = _merge_summaries(parts)
    logger.info("摘要完成")
    return merged
