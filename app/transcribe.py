import logging
import math
import os
import tempfile
from pathlib import Path

from app.models import MeetingTranscript

logger = logging.getLogger(__name__)

AUDIO_FORMATS = {".mp3", ".mp4", ".wav", ".m4a", ".webm", ".mpeg", ".mpga"}
TEXT_FORMATS = {".txt"}
SUPPORTED_FORMATS = AUDIO_FORMATS | TEXT_FORMATS

# 本地 Whisper 模型大小：tiny / base / small / medium
# small 在 CPU 上約每分鐘音檔需 1-2 分鐘處理，準確率不錯
LOCAL_WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")


def _transcribe_with_openai_api(file_path: str) -> MeetingTranscript:
    """呼叫 OpenAI Whisper API 轉錄音檔（需要 OPENAI_API_KEY）。"""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    with open(file_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
        )

    duration = getattr(response, "duration", None)
    language = getattr(response, "language", "zh")
    logger.info("Whisper API 轉錄完成，語言: %s，時長: %s 秒", language, duration)

    return MeetingTranscript(
        text=response.text,
        duration=duration,
        language=language,
    )


def _transcribe_with_faster_whisper(file_path: str, model_size: str = None) -> MeetingTranscript:
    """使用本地 faster-whisper 模型轉錄音檔（不需要 API Key）。"""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "缺少 faster-whisper 套件。請執行：pip install faster-whisper"
        )

    size = model_size or LOCAL_WHISPER_MODEL
    logger.info("載入本地 Whisper 模型（%s），首次使用會自動下載…", size)

    model = WhisperModel(size, device="cpu", compute_type="int8")

    logger.info("開始轉錄：%s", file_path)
    segments, info = model.transcribe(file_path, beam_size=5, language="zh")

    text_parts = []
    total_duration = 0.0
    logprobs = []
    for seg in segments:
        text_parts.append(seg.text.strip())
        total_duration = seg.end
        if seg.avg_logprob is not None:
            logprobs.append(seg.avg_logprob)

    full_text = " ".join(text_parts)

    # 將平均 log probability 轉換為 0–100 信心分數
    confidence = None
    if logprobs:
        avg_logprob = sum(logprobs) / len(logprobs)
        # logprob 通常在 -1 ~ 0 之間，-0.5 以上算準確
        confidence = round(min(max(math.exp(avg_logprob) * 100, 0), 100), 1)

    logger.info(
        "本地轉錄完成，語言: %s，時長: %.1f 秒，字元數: %d，信心分數: %s",
        info.language,
        total_duration,
        len(full_text),
        confidence,
    )

    return MeetingTranscript(
        text=full_text,
        duration=total_duration,
        language=info.language or "zh",
        confidence=confidence,
    )


def transcribe_audio_bytes(audio_bytes: bytes, filename: str, model_size: str = None) -> MeetingTranscript:
    """
    從上傳的音檔 bytes 轉錄逐字稿（Streamlit file_uploader 使用此介面）。

    策略：有 OPENAI_API_KEY → Whisper API，否則 → 本地 faster-whisper
    """
    suffix = Path(filename).suffix.lower()

    if suffix not in AUDIO_FORMATS:
        raise ValueError(f"不支援的音檔格式：{suffix}")

    # 寫入暫存檔再處理
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        if os.environ.get("OPENAI_API_KEY"):
            return _transcribe_with_openai_api(tmp_path)
        else:
            return _transcribe_with_faster_whisper(tmp_path, model_size)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _read_text_file(file_path: str) -> MeetingTranscript:
    """直接讀取 .txt 文字檔作為逐字稿。"""
    text = Path(file_path).read_text(encoding="utf-8")
    logger.info("讀取文字檔完成，共 %d 字元", len(text))
    return MeetingTranscript(text=text, language="zh")


def transcribe_audio(file_path: str) -> MeetingTranscript:
    """
    將音檔或文字檔轉為逐字稿（FastAPI 端點使用此介面）。

    - .txt 檔：直接讀取
    - 音檔：有 OPENAI_API_KEY → Whisper API，否則 → 本地 faster-whisper
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"找不到檔案：{file_path}")

    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(
            f"不支援的格式：{suffix}。"
            f"支援格式：{', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    if suffix in TEXT_FORMATS:
        return _read_text_file(file_path)

    logger.info("開始轉錄音檔: %s", file_path)

    if os.environ.get("OPENAI_API_KEY"):
        return _transcribe_with_openai_api(file_path)
    else:
        return _transcribe_with_faster_whisper(file_path)
