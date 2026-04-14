import logging
import time
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models import MeetingSummary, TranscribeResponse
from app.summarize import summarize_transcript
from app.transcribe import transcribe_audio

# ---------------------------------------------------------------------------
# Logging 設定
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App 生命週期
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Meeting Assistant API 啟動")
    yield
    logger.info("Meeting Assistant API 關閉")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="智慧逐字稿分析助理",
    description="上傳音檔或任意逐字稿，自動產出摘要與重點整理",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request Logging Middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    logger.info("[%s] %s %s", request_id, request.method, request.url.path)
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    logger.info(
        "[%s] 完成 status=%d 耗時=%.1fms",
        request_id,
        response.status_code,
        elapsed,
    )
    return response


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class SummarizeTextRequest(BaseModel):
    text: str
    language: str = "zh"
    prompt_version: str = "v3"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", summary="健康檢查")
async def health():
    return {"status": "ok", "service": "meeting-assistant"}


@app.post(
    "/transcribe",
    response_model=TranscribeResponse,
    summary="上傳音檔，轉錄並摘要",
)
async def transcribe_endpoint(file: UploadFile = File(...)):
    """
    接受音檔（mp3 / mp4 / wav / m4a），呼叫 Whisper API 轉錄後
    再用 GPT-4o-mini 產出結構化摘要。
    """
    import tempfile
    from pathlib import Path

    suffix = Path(file.filename or "audio").suffix.lower()
    allowed = {".mp3", ".mp4", ".wav", ".m4a", ".webm", ".mpeg", ".mpga"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"不支援的格式：{suffix}。支援：{', '.join(allowed)}",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        transcript = transcribe_audio(tmp_path)
        summary = summarize_transcript(transcript)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return TranscribeResponse(transcript=transcript, summary=summary)


@app.post(
    "/summarize-text",
    response_model=MeetingSummary,
    summary="直接貼逐字稿，產出摘要與重點整理",
)
async def summarize_text_endpoint(body: SummarizeTextRequest):
    """
    直接傳入任意逐字稿文字，產出摘要、重點整理、關鍵詞。
    """
    from app.models import MeetingTranscript

    if not body.text.strip():
        raise HTTPException(status_code=400, detail="逐字稿內容不可為空")

    transcript = MeetingTranscript(text=body.text, language=body.language)
    try:
        summary = summarize_transcript(transcript, prompt_version=body.prompt_version)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return summary
