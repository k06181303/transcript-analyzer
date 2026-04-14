"""
智慧逐字稿分析助理 — Streamlit UI
"""

import sys
from pathlib import Path

# 確保 app 套件可被找到
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from app.models import MeetingTranscript
from app.summarize import summarize_transcript

# ---------------------------------------------------------------------------
# 頁面設定
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="智慧逐字稿分析助理",
    page_icon="📝",
    layout="wide",
)

# ---------------------------------------------------------------------------
# 共用：渲染分析結果
# ---------------------------------------------------------------------------
def render_result(result, used_version: str, source_text: str):
    st.markdown("#### 摘要")
    st.info(result.summary)

    st.markdown("#### 重點整理")
    for i, kp in enumerate(result.key_points, 1):
        st.markdown(f"**{i}.** {kp}")

    if result.keywords:
        st.markdown("#### 關鍵詞")
        st.markdown(" ".join(f"`{kw}`" for kw in result.keywords))

    if result.participants:
        st.markdown("#### 發言者")
        st.markdown("、".join(result.participants))

    st.divider()

    report_lines = [
        f"# 逐字稿分析報告（prompt={used_version}）",
        "",
        "## 摘要",
        result.summary,
        "",
        "## 重點整理",
    ]
    for i, kp in enumerate(result.key_points, 1):
        report_lines.append(f"{i}. {kp}")

    if result.keywords:
        report_lines += ["", "## 關鍵詞", "、".join(result.keywords)]
    if result.participants:
        report_lines += ["", "## 發言者", "、".join(result.participants)]

    report_lines += [
        "", "---",
        "原始逐字稿（前 300 字）：",
        source_text[:300] + "…",
    ]

    report_text = "\n".join(report_lines)
    summary_only = f"【摘要】\n{result.summary}\n\n【重點整理】\n" + "\n".join(
        f"{i}. {kp}" for i, kp in enumerate(result.key_points, 1)
    )

    col_dl, col_copy = st.columns(2)
    with col_dl:
        st.download_button(
            label="⬇️ 下載報告 (.txt)",
            data=report_text.encode("utf-8"),
            file_name="analysis_report.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col_copy:
        st.download_button(
            label="📋 複製摘要 (.txt)",
            data=summary_only.encode("utf-8"),
            file_name="summary.txt",
            mime="text/plain",
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# 標題
# ---------------------------------------------------------------------------
st.title("📝 智慧逐字稿分析助理")
st.caption("貼入逐字稿文字，或上傳音檔（MP3/WAV/M4A…），自動產出摘要與重點整理")

st.divider()

# ---------------------------------------------------------------------------
# 側邊欄：設定
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 分析設定")

    prompt_version = st.selectbox(
        "Prompt 版本",
        options=["v3", "v2", "v1"],
        index=0,
        help="v3 = 主題掃描策略（準確性最高）｜v2 = 類別清單策略｜v1 = 通用寬鬆版",
    )

    version_desc = {
        "v1": "🔵 寬鬆通用，靠模型自行判斷重點",
        "v2": "🟠 類別清單策略，強制涵蓋數字/決定/建議",
        "v3": "🟢 主題掃描策略，準確性最高（建議使用）",
    }
    st.info(version_desc[prompt_version])

    st.divider()
    st.markdown("**支援類型**")
    st.markdown("- 會議記錄\n- 訪談稿\n- 演講稿\n- Podcast\n- 腦力激盪\n- 其他逐字稿")

    st.divider()
    st.markdown("**音檔轉錄設定**")
    whisper_model = st.selectbox(
        "Whisper 模型大小",
        options=["tiny", "base", "small", "medium"],
        index=2,
        help="tiny = 最快但較不準確 / small = 速度與準確率平衡（建議）/ medium = 最準但較慢",
    )
    st.caption("首次使用會自動下載模型（small ≈ 480MB）")

# ---------------------------------------------------------------------------
# 輸入頁籤：文字 / 音檔
# ---------------------------------------------------------------------------
tab_text, tab_audio = st.tabs(["📄 貼入文字", "🎙️ 上傳音檔"])

# ── 文字頁籤 ─────────────────────────────────────────────────────────────
with tab_text:
    col_input, col_output = st.columns([1, 1], gap="large")

    with col_input:
        st.subheader("📄 輸入逐字稿")

        sample_dir = Path(__file__).parent / "sample"
        sample_files = {
            "訪談：AI 可解釋性研究": sample_dir / "interview_transcript.txt",
            "演講：技術債管理": sample_dir / "lecture_transcript.txt",
            "Podcast：新創公司 B 輪": sample_dir / "podcast_transcript.txt",
            "腦力激盪：App 留存率": sample_dir / "brainstorm_transcript.txt",
            "會議：產品規劃": sample_dir / "sample_transcript.txt",
        }

        selected_sample = st.selectbox(
            "載入範例",
            options=["（自行輸入）"] + list(sample_files.keys()),
            index=0,
        )

        default_text = ""
        if selected_sample != "（自行輸入）":
            path = sample_files[selected_sample]
            if path.exists():
                default_text = path.read_text(encoding="utf-8")

        transcript_text = st.text_area(
            "逐字稿內容",
            value=default_text,
            height=420,
            placeholder="請在此貼入逐字稿文字…",
        )

        char_count = len(transcript_text)
        st.caption(f"字元數：{char_count:,}")

        analyze_text_btn = st.button(
            "🚀 開始分析",
            key="analyze_text",
            type="primary",
            use_container_width=True,
            disabled=(char_count < 10),
        )

    with col_output:
        st.subheader("📊 分析結果")

        if analyze_text_btn:
            if not transcript_text.strip():
                st.warning("請先輸入逐字稿內容。")
            else:
                with st.spinner(f"使用 prompt {prompt_version} 分析中…"):
                    try:
                        transcript = MeetingTranscript(text=transcript_text, language="zh")
                        result = summarize_transcript(transcript, prompt_version=prompt_version)
                        st.session_state["result"] = result
                        st.session_state["prompt_version"] = prompt_version
                        st.session_state["transcript_text"] = transcript_text
                        st.session_state["active_tab"] = "text"
                    except RuntimeError as e:
                        st.error(f"分析失敗：{e}")
                        st.stop()

        if "result" in st.session_state and st.session_state.get("active_tab") == "text":
            render_result(
                st.session_state["result"],
                st.session_state.get("prompt_version", "v3"),
                st.session_state.get("transcript_text", ""),
            )
        else:
            st.markdown(
                "<div style='color:#aaa; padding:60px 0; text-align:center;'>"
                "輸入逐字稿後點擊「開始分析」</div>",
                unsafe_allow_html=True,
            )

# ── 音檔頁籤 ──────────────────────────────────────────────────────────────
with tab_audio:
    col_audio_in, col_audio_out = st.columns([1, 1], gap="large")

    with col_audio_in:
        st.subheader("🎙️ 上傳音檔")

        uploaded_file = st.file_uploader(
            "選擇音檔",
            type=["mp3", "wav", "m4a", "mp4", "webm", "mpeg"],
            help="支援 MP3 / WAV / M4A / MP4 / WebM",
        )

        if uploaded_file is not None:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            st.audio(uploaded_file)
            st.caption(f"檔案：{uploaded_file.name}　大小：{file_size_mb:.1f} MB")

            est_min = round(file_size_mb / 1.5)
            st.info(
                f"預估音檔長度約 {est_min} 分鐘。\n\n"
                f"使用本地 Whisper **{whisper_model}** 模型轉錄（無需 API Key）。\n"
                "首次執行會自動下載模型，請耐心等候。"
            )

            analyze_audio_btn = st.button(
                "🎙️ 轉錄並分析",
                key="analyze_audio",
                type="primary",
                use_container_width=True,
            )
        else:
            st.markdown(
                "<div style='color:#aaa; padding:40px 0; text-align:center;'>"
                "請上傳音檔（MP3、WAV、M4A…）</div>",
                unsafe_allow_html=True,
            )
            analyze_audio_btn = False

    with col_audio_out:
        st.subheader("📊 分析結果")

        if analyze_audio_btn and uploaded_file is not None:
            from app.transcribe import transcribe_audio_bytes

            audio_bytes = uploaded_file.read()

            with st.spinner(f"⏳ 第 1 步：轉錄音檔（Whisper {whisper_model}）… 44 分鐘音檔約需 10-20 分鐘"):
                try:
                    transcript_obj = transcribe_audio_bytes(
                        audio_bytes,
                        uploaded_file.name,
                        model_size=whisper_model,
                    )
                    st.session_state["audio_transcript"] = transcript_obj
                except RuntimeError as e:
                    st.error(f"轉錄失敗：{e}")
                    st.stop()

            duration_str = ""
            if transcript_obj.duration:
                mins = int(transcript_obj.duration // 60)
                secs = int(transcript_obj.duration % 60)
                duration_str = f"（音檔時長：{mins} 分 {secs} 秒）"

            confidence_str = ""
            if transcript_obj.confidence is not None:
                confidence_str = f"　信心分數：{transcript_obj.confidence}%"
            st.success(f"✅ 轉錄完成 {duration_str}，共 {len(transcript_obj.text):,} 字元{confidence_str}")

            with st.spinner(f"⏳ 第 2 步：使用 prompt {prompt_version} 摘要分析…"):
                try:
                    result = summarize_transcript(transcript_obj, prompt_version=prompt_version)
                    st.session_state["result"] = result
                    st.session_state["prompt_version"] = prompt_version
                    st.session_state["transcript_text"] = transcript_obj.text
                    st.session_state["active_tab"] = "audio"
                except RuntimeError as e:
                    st.error(f"摘要失敗：{e}")
                    st.stop()

        if "result" in st.session_state and st.session_state.get("active_tab") == "audio":
            render_result(
                st.session_state["result"],
                st.session_state.get("prompt_version", "v3"),
                st.session_state.get("transcript_text", ""),
            )

            if "audio_transcript" in st.session_state:
                with st.expander("📝 查看轉錄原文"):
                    st.text_area(
                        "逐字稿",
                        value=st.session_state["audio_transcript"].text,
                        height=300,
                        disabled=True,
                    )
        else:
            st.markdown(
                "<div style='color:#aaa; padding:60px 0; text-align:center;'>"
                "上傳音檔後點擊「轉錄並分析」</div>",
                unsafe_allow_html=True,
            )
