---
title: 智慧逐字稿分析助理
emoji: 📝
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 📝 智慧逐字稿分析助理

上傳會議錄音或貼入逐字稿，自動產出結構化摘要、重點整理、關鍵詞與發言者分析。  
不限於會議記錄，訪談、演講、Podcast、腦力激盪等各類型逐字稿均適用。  
透過三個版本的 Prompt 設計與 LLM-as-judge Eval Pipeline，持續優化輸出品質。

## Demo

![demo](assets/demo.gif)

🔗 **線上試用：** [huggingface.co/spaces/k06181303/transcript-analyzer](https://huggingface.co/spaces/k06181303/transcript-analyzer)

---

## 功能列表

| 功能 | 說明 |
|------|------|
| 通用逐字稿分析 | 支援會議、訪談、演講、Podcast、腦力激盪等類型 |
| 音檔轉錄 | 本地 faster-whisper（免 API Key），支援 MP3/WAV/M4A/MP4 |
| 結構化摘要 | Claude Haiku 產出繁體中文摘要，強制 Pydantic 結構輸出 |
| 重點整理 | 5–8 項完整句子，逐主題覆蓋，不遺漏後半段 |
| 關鍵詞萃取 | 3–8 個核心名詞 / 術語 |
| 發言者辨識 | 自動偵測發言者，無發言者時回傳空陣列 |
| 長逐字稿分段 | 以 tiktoken 計算 token 數，超過上限自動切段後合併 |
| Prompt 自動優化 | 依 Whisper 信心分數調整容錯策略；逐字稿結構分析自動注入 prompt |
| Prompt 版本選擇 | v1 通用 / v2 類別清單 / v3 主題掃描（預設） |
| 下載報告 | 一鍵下載完整分析報告或純摘要 .txt |

---

## 系統架構

```
輸入
  ├── 音檔（MP3/WAV/M4A…）
  │     └── app/transcribe.py
  │           ├── faster-whisper（本地，免費）
  │           │     └── 回傳逐字稿 + 信心分數（0–100）
  │           └── OpenAI Whisper API（有 OPENAI_API_KEY 時優先）
  │
  └── 逐字稿文字（直接貼入）
        └── MeetingTranscript(text, duration, language, confidence)
                │
                ▼
        app/summarize.py
          ├── _analyze_structure()    逐字稿結構分析（免費）
          │     ├── 發言者數量偵測
          │     ├── 時間戳偵測
          │     ├── 問答密度分析
          │     └── 領域偵測（技術/商業/學術）
          │
          ├── _build_confidence_note()  Whisper 信心分數 → prompt 容錯策略
          │
          ├── tiktoken                  長逐字稿自動分段
          ├── instructor                強制結構化輸出（Pydantic）
          └── Claude Haiku（Anthropic API）
                │
                ▼
        MeetingSummary
          ├── summary       整體摘要（繁體中文）
          ├── key_points    重點整理（5–8 項）
          ├── participants  發言者名單
          └── keywords      關鍵詞（3–8 個）
                │
                ▼
        streamlit_app.py（UI）
          ├── 摘要 / 重點 / 關鍵詞 / 發言者 分區呈現
          └── 下載完整報告 / 摘要 .txt
```

---

## 安裝與執行

### 環境需求

- Python 3.11+
- [Anthropic API Key](https://console.anthropic.com/)
- ffmpeg（音檔轉錄需要）：`choco install ffmpeg` 或 `winget install ffmpeg`

### 步驟

```powershell
git clone https://github.com/k06181303/transcript-analyzer.git
cd transcript-analyzer

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
# 用文字編輯器開啟 .env，填入 ANTHROPIC_API_KEY=sk-ant-...

streamlit run streamlit_app.py
```

瀏覽器自動開啟 `http://localhost:8501`

### Docker

```powershell
docker build -t transcript-analyzer .
docker run -p 7860:7860 -e ANTHROPIC_API_KEY=sk-ant-... transcript-analyzer
```

---

## API 使用範例

啟動 FastAPI 伺服器（選用）：

```powershell
uvicorn app.main:app --reload
```

**文字摘要：**

```bash
curl -X POST http://localhost:8000/summarize-text \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"王小明：今天開會主題是用戶留存率下降問題...\", \"language\": \"zh\"}"
```

**回傳範例：**

```json
{
  "summary": "會議討論用戶留存率下降 8% 的問題，決定優先修復 N+1 查詢並評估 CDN 方案。",
  "key_points": [
    "用戶留存率環比下降 8%，主因為首頁載入速度超過 5 秒",
    "李小華負責本週修復首頁 API 的 N+1 查詢問題"
  ],
  "participants": ["王小明", "李小華", "陳大偉"],
  "keywords": ["留存率", "N+1 查詢", "CDN", "效能優化"]
}
```

---

## Eval 結果（LLM-as-judge）

使用 Claude Haiku 作為評審，對 5 種類型逐字稿（會議、訪談、演講、Podcast、腦力激盪）進行兩輪評估。

### 第一輪（v1 vs v2）

| 指標 | v1 | v2 | 說明 |
|------|:--:|:--:|----|
| 完整度（/5） | 4.20 | 3.60 | v1 較佳 |
| 準確性（/5） | 4.20 | 3.20 | v1 較佳 |
| 格式正確率 | 100% | 100% | 持平 |
| key_points 涵蓋率 | 80% | 73% | v1 較佳 |

發現問題：interview 類型 key_points 不足 3 項；v2 與 v1 差異過小。

### 第二輪（v1 vs v2 更新版 vs v3）

| 指標 | v1 | v2（更新） | v3（預設） |
|------|:--:|:----------:|:----------:|
| 完整度（/5） | 4.00 | 3.60 | **4.00** |
| 準確性（/5） | 4.00 | 3.20 | **4.60** |
| 格式正確率 | 100% | 100% | **100%** |
| key_points 涵蓋率 | 76% | 64% | **76%** |

**結論：** v3（主題掃描策略）準確性（4.60）明顯優於 v1/v2，涵蓋率與 v1 持平，設為預設版本。

---

## 踩坑紀錄

### 1. Windows 終端機顯示中文亂碼，以為摘要功能壞了

**問題：** 執行摘要後終端機輸出全是亂碼，懷疑 API 回傳錯誤。  
**原因：** Windows cmd / PowerShell 預設編碼是 CP950，無法正確顯示 UTF-8 中文。  
**解法：** 把摘要結果寫成 JSON 檔（`encoding='utf-8'`）再開啟確認，終端機顯示問題不影響實際資料。

### 2. FastAPI `/summarize-text` 回傳 502，API Key 明明已設定

**問題：** 呼叫 API 時回傳 502 Bad Gateway，但 `.env` 裡 Key 確實存在。  
**原因：** `main.py` 啟動時沒有執行 `load_dotenv()`，伺服器找不到環境變數。  
**解法：** 在 `main.py` 最上方加上 `from dotenv import load_dotenv; load_dotenv()`。

### 3. HuggingFace 拒絕 push，說有 binary file

**問題：** `git push` 到 HuggingFace Space 時被拒絕，報錯 `your push was rejected because it contains binary files`。  
**原因：** HuggingFace 新版改用 Xet 儲存系統，不接受一般 git 追蹤的 PNG/binary 檔案，且會掃描整個 commit 歷史。  
**解法：** 把 `eval/eval_report.png` 加入 `.gitignore`，再用 `git checkout --orphan` 建立無歷史的乾淨分支重新 push。

### 4. Prompt v2 在訪談類型效果反而比 v1 差

**問題：** 設計 v2 加入更多結構化規則，預期會比 v1 好，結果 Eval 分數全面下降。  
**原因：** 過度約束讓模型在訪談這類非結構化內容上無法靈活發揮，強制套用商業/技術類別清單反而造成雜訊。  
**解法：** 設計 v3 改採「先掃描主題、再逐主題萃取」策略，讓模型自行決定主題數量，準確性提升至 4.60。

---

## 未來規劃

- [ ] **RAG 整合**：將歷史逐字稿向量化存入資料庫，支援跨會議查詢（「上週討論過哪些 API 相關決策？」）
- [ ] **Eval 自動選版本**：根據逐字稿類型從 eval 結果自動選最佳 prompt 版本
- [ ] **說話者分離（Speaker Diarization）**：整合 pyannote.audio，自動標注「誰在什麼時間說了什麼」
- [ ] **多語言支援**：英文逐字稿自動翻譯後分析
- [ ] **摘要對比模式**：同一份逐字稿用不同 prompt 版本同時輸出，方便比較差異

---

## 專案結構

```
transcript-analyzer/
├── streamlit_app.py       # Streamlit UI 進入點
├── Dockerfile             # HuggingFace Spaces Docker 部署
├── requirements.txt
├── app/
│   ├── models.py          # Pydantic 資料模型
│   ├── summarize.py       # Claude Haiku 摘要（tiktoken + instructor + 結構分析）
│   ├── transcribe.py      # 音檔轉文字（faster-whisper，含信心分數）
│   └── main.py            # FastAPI（選用）
├── prompts/
│   ├── v1.txt             # 通用寬鬆版
│   ├── v2.txt             # 類別清單版
│   └── v3.txt             # 主題掃描版（預設）
├── eval/
│   ├── golden_dataset.json
│   ├── evaluator.py       # LLM-as-judge（Claude Haiku）
│   ├── run_eval.py        # 批次評估
│   └── visualize.py       # 產出比較圖表
├── sample/                # 5 種類型範例逐字稿
├── assets/
│   └── demo.gif
└── tests/                 # pytest 測試（25 項）
```

## 環境變數

| 變數 | 說明 | 必填 |
|------|------|:----:|
| `ANTHROPIC_API_KEY` | Anthropic API Key | ✅ |
| `OPENAI_API_KEY` | OpenAI API Key（用 Whisper API 時才需要） | ❌ |
| `WHISPER_MODEL` | faster-whisper 模型大小（預設 `small`） | ❌ |

## License

MIT © 2026 k06181303
