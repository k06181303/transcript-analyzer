"""
批次執行 eval：對所有 golden_dataset 跑 v1 和 v2，輸出 eval_results.json

使用方式：
  python eval/run_eval.py
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 讓 script 能找到 app 套件
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app.models import MeetingTranscript
from app.summarize import summarize_transcript
from eval.evaluator import evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATASET_PATH = ROOT / "eval" / "golden_dataset.json"
OUTPUT_PATH = ROOT / "eval" / "eval_results.json"
PROMPT_VERSIONS = ["v1", "v2", "v3"]


def run():
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    results = []

    for item in dataset:
        sample_path = ROOT / item["sample_file"]
        original_text = sample_path.read_text(encoding="utf-8")
        transcript = MeetingTranscript(text=original_text, language="zh")

        for version in PROMPT_VERSIONS:
            logger.info("評估 [%s] prompt=%s ...", item["id"], version)

            # 產出摘要
            summary_obj = summarize_transcript(transcript, prompt_version=version)

            # LLM 評分
            score = evaluate(
                original_text=original_text,
                golden_summary=item["golden_summary"],
                golden_key_points=item["golden_key_points"],
                model_summary=summary_obj.summary,
                model_key_points=summary_obj.key_points,
            )

            results.append({
                "id": item["id"],
                "type": item["type"],
                "prompt_version": version,
                "model_summary": summary_obj.summary,
                "model_key_points": summary_obj.key_points,
                "scores": {
                    "completeness": score.completeness,
                    "accuracy": score.accuracy,
                    "format_ok": score.format_ok,
                    "coverage_rate": score.coverage_rate,
                },
                "reasoning": score.reasoning,
            })

            logger.info(
                "  completeness=%d accuracy=%d format_ok=%d coverage=%.2f",
                score.completeness, score.accuracy, score.format_ok, score.coverage_rate,
            )

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("結果已儲存至 %s", OUTPUT_PATH)

    # 印出摘要統計
    print("\n=== 評估結果摘要 ===")
    for version in PROMPT_VERSIONS:
        v_results = [r for r in results if r["prompt_version"] == version]
        avg_completeness = sum(r["scores"]["completeness"] for r in v_results) / len(v_results)
        avg_accuracy = sum(r["scores"]["accuracy"] for r in v_results) / len(v_results)
        avg_format = sum(r["scores"]["format_ok"] for r in v_results) / len(v_results)
        avg_coverage = sum(r["scores"]["coverage_rate"] for r in v_results) / len(v_results)
        print(f"\nPrompt {version}:")
        print(f"  完整度：{avg_completeness:.2f} / 5")
        print(f"  準確性：{avg_accuracy:.2f} / 5")
        print(f"  格式正確率：{avg_format:.0%}")
        print(f"  key_points 涵蓋率：{avg_coverage:.0%}")


if __name__ == "__main__":
    run()
