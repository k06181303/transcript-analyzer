# 智慧會議記錄助理 — 專案進度追蹤

> 最後更新：2026-04-14（Phase 4 新增 Prompt 自動優化功能）
> 掃描方式：自動讀取專案檔案結構 + 測試結果

---

## 整體進度

| Phase | 名稱 | 完成度 | 狀態 |
|-------|------|--------|------|
| 1 | 基礎 Pipeline 通串 | 100% (17/17) | ✅ 完成 |
| 2 | Prompt 設計 + 結構化輸出 | 100% (8/8) | ✅ 完成 |
| 3 | Eval Pipeline | 100% (8/8) | ✅ 完成 |
| 4 | 包裝成可展示的產品 | 92% (11/12) | 🔄 進行中 |
| 5 | 作品集收尾 | 0% (0/5) | ⏳ 未開始 |

**總體進度：89% (44/50)**

---

## Phase 1：基礎 Pipeline 通串

> 目標：1–2 週 ｜ 完成條件：伺服器跑起來，/summarize-text 能把任意逐字稿轉成結構化摘要

**進度：100% (17/17)** ✅

### 環境建置
- [x] 建立虛擬環境（venv）
- [x] 安裝套件：anthropic, fastapi, uvicorn, python-dotenv, httpx
- [x] 建立 .env 與 .env.example（放 ANTHROPIC_API_KEY）

### 核心程式
- [x] 建立 app/models.py：MeetingTranscript / MeetingSummary / TranscribeResponse
- [x] 建立 app/transcribe.py：讀取 .txt 逐字稿或呼叫 Whisper API，含三層 error handling
- [x] 建立 app/summarize.py：呼叫 claude-haiku-4-5-20251001，JSON mode，超過 3000 字自動分段
- [x] 建立 app/main.py：FastAPI，/health、POST /transcribe、POST /summarize-text、CORS、request logging

### 通用化改版（2026-04-12）
- [x] 將分析範圍從「會議逐字稿」擴展為**任意逐字稿**（訪談、演講、課程、會議等）
- [x] 輸出欄位調整：移除 `action_items`、`decisions`，新增 `key_points`（重點整理）
- [x] `participants` 改為選填：無明確發言者時回傳空陣列
- [x] System prompt 更新為通用逐字稿分析版本

### 測試與文件
- [x] 建立 tests/test_transcribe.py：12 個測試全數通過 ✅
- [x] 建立 sample/sample_transcript.txt
- [x] 建立 README.md：專案說明、Windows 安裝步驟、API 使用範例
- [x] 建立 .gitignore：排除 .env 和 venv/

### 驗收
- [x] 填入 ANTHROPIC_API_KEY 到 .env
- [x] 啟動伺服器：`uvicorn app.main:app --reload`（可用）
- [x] 瀏覽器打開 http://127.0.0.1:8000/docs 確認 API 文件正常
- [x] 用 /summarize-text 端點測試摘要功能，確認回傳結構化 JSON

---

## Phase 2：Prompt 設計 + 結構化輸出

> 目標：1–2 週 ｜ 完成條件：Prompt v2 的摘要完整度優於 v1，有數據佐證

**進度：100% (8/8)** ✅

- [x] 建立 prompts/ 資料夾，把現有 system prompt 存為 prompts/v1.txt 版本化
- [x] 用 Pydantic + instructor 套件強制結構化輸出（取代手動 JSON parse）
- [x] 實作長逐字稿分段策略：用 tiktoken 計算 token 數，超過上限自動切段（取代字元數）
- [x] 實作分段摘要合併邏輯：各段 key_points → 最終統整摘要
- [x] 支援有發言人 tag 的逐字稿（格式：`[Alice]: ...`），v2 prompt 自動偵測並標注
- [x] 設計 Prompt v2：強化 key_points 精準度（要求「主詞＋動作＋結果」完整句）
- [x] 建立 tests/test_prompts.py：13 個測試全數通過，覆蓋會議、訪談、演講三種類型 ✅
- [x] 確認 summary / key_points / keywords 對各類逐字稿都有合理輸出

---

## Phase 3：Eval Pipeline

> 目標：1 週 ｜ 完成條件：有圖表顯示 Prompt v1 vs v2 各指標比較

**進度：100% (8/8)** ✅

- [x] 收集或製作 5 筆不同類型的逐字稿（會議、訪談、演講、Podcast、腦力激盪）
- [x] 建立 eval/golden_dataset.json：每筆含逐字稿路徑 + 人工標注的理想摘要與重點
- [x] 設計評估標準：完整度（0–5）、準確性（0–5）、格式正確率（0/1）、key_points 涵蓋率（%）
- [x] 實作 eval/evaluator.py：用 LLM-as-judge（Claude Haiku）自動打分，instructor 強制結構化輸出
- [x] 實作 eval/run_eval.py：批次跑 v1/v2 × 5 筆，輸出 eval/eval_results.json
- [x] 用 pandas + matplotlib 把結果視覺化，輸出 eval/eval_report.png
- [x] 比較 v1 vs v2 結果（見下方分析）
- [x] eval_report.png 已產出（執行 `python eval/visualize.py` 可重新產生）

### Eval 結果分析（2026-04-12，第一輪）

| 指標 | v1 | v2 | 差異 |
|------|----|----|------|
| 完整度（/5） | 4.20 | 3.80 | v1 +0.40 |
| 準確性（/5） | 4.20 | 3.40 | v1 +0.80 |
| 格式正確率 | 100% | 100% | 持平 |
| key_points 涵蓋率 | 80% | 73% | v1 +7% |

**發現問題**：① interview 類型 key_points 不足 3 項；② v2 與 v1 在訪談類型輸出差異過小

### Prompt 迭代優化（2026-04-12）

- [x] 更新 v2：強制 key_points 最少 5 項，加入類別涵蓋清單（數字/發現/決定/行動/建議）
- [x] 新增 v3：採「先掃描主題、再逐主題萃取」策略，從根本解決漏項問題

### Eval 結果分析（2026-04-12，第二輪）

| 指標 | v1 | v2（更新後） | v3（新） |
|------|----|----|------|
| 完整度（/5） | 4.00 | 3.60 | **4.00** |
| 準確性（/5） | 4.00 | 3.20 | **4.60** |
| 格式正確率 | 100% | 100% | 100% |
| key_points 涵蓋率 | 76% | 64% | **76%** |

### API 實測 key_points 項數（2026-04-12）

| 類型 | v1 | v2 | v3 |
|------|----|----|-----|
| interview | 5 項 ✅ | 6 項 ✅ | 6 項 ✅ |
| lecture | 6 項 ✅ | 5 項 ✅ | 6 項 ✅ |
| brainstorm | 6 項 ✅ | 6 項 ✅ | 7 項 ✅ |

**結論**：v3（主題掃描策略）在準確性（4.60）上明顯優於 v1/v2，涵蓋率與 v1 持平，同時解決了 key_points 不足的問題。建議後續以 v3 為基礎繼續迭代。

---

## Phase 4：包裝成可展示的產品

> 目標：3–5 天 ｜ 完成條件：有公開網址可試用，README 有 demo 影片

**進度：92% (11/12)** 🔄

- [x] 安裝 streamlit（v1.56.0）
- [x] 建立 streamlit_app.py：雙欄佈局，左側輸入、右側輸出
- [x] UI 功能：貼入逐字稿文字、載入範例（5 種類型）、選擇 prompt 版本（v1/v2/v3）
- [x] UI 顯示：摘要、重點整理、關鍵詞、發言者分區塊呈現
- [x] UI 功能：下載完整報告 .txt、下載摘要 .txt（瀏覽器限制無法直接複製到剪貼簿）
- [x] 本地測試：3 種 sample 全數通過（interview/lecture/brainstorm），預設使用 v3
- [x] 建立 Dockerfile（port 7860，Docker SDK）
- [x] 部署到 Hugging Face Spaces（Docker）：https://huggingface.co/spaces/k06181303/transcript-analyzer
- [x] ANTHROPIC_API_KEY 設為 Space Secret，線上版本狀態 RUNNING ✅

### Prompt 自動優化（2026-04-14）
- [x] `MeetingTranscript` 新增 `confidence` 欄位（Whisper 信心分數 0–100）
- [x] `transcribe.py`：擷取 faster-whisper `avg_logprob`，轉換為信心分數並回傳
- [x] `summarize.py`：`_build_confidence_note()` — 依信心分數自動調整 system prompt 容錯策略（高≥75% 不調整／中 40–74% 提示推斷錯誤詞彙／低<40% 聚焦整體語意）
- [x] `summarize.py`：`_analyze_structure()` — 純文字啟發式分析逐字稿結構，偵測發言者數量、時間戳、問答密度、領域（技術/商業/學術）、長度，免費注入 user message
- [x] 三個 prompt 版本（v1/v2/v3）加強繁體中文強制規定（禁止簡體或英文輸出）
- [ ] 錄製 30 秒 demo 影片，展示完整流程並放進 README.md

---

## Phase 5：作品集收尾

> 目標：2–3 天 ｜ 完成條件：GitHub 整潔、README 完整、部落格文章、線上 demo

**進度：0% (0/5)** ⏳

- [ ] README.md 完整版：專案背景（通用逐字稿分析）、技術架構圖、eval 結果、踩坑紀錄、未來規劃
- [ ] 寫一篇技術部落格文章（Medium 或 Dev.to）
- [ ] GitHub repo 整理：清理檔案、確認 .gitignore、加上 License
- [ ] 確認 repo 有清楚的 commit history（每個 Phase 一個 commit）
- [ ] 在 LinkedIn 或個人網站更新作品集，附上 GitHub 連結和 demo 網址

---

## 目前狀態

### 卡關 / 待確認
- HuggingFace Space 已建立，但 `meeting-assistant/` 尚未初始化獨立 git repo，程式碼還未 push 上去

### 下一步
1. **Phase 4 收尾**：
   - 在 `meeting-assistant/` 初始化 git repo，push 到 HuggingFace Space
   - 確認線上版本正常運作
   - 錄製 30 秒 demo 影片放進 README.md
2. **Phase 5**：整理 GitHub repo、撰寫完整 README、寫技術文章

---

## 更新說明

| 指令 | 動作 |
|------|------|
| 「更新進度」 | 重新掃描專案資料夾，自動更新所有 [x] 狀態與百分比 |
| 「我完成了 XXX」 | 把對應項目標記為 [x] 並更新百分比 |
