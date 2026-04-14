"""
讀取 eval_results.json，繪製 v1 vs v2 各指標比較圖，輸出 eval_report.png

使用方式：
  python eval/visualize.py
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 無顯示器環境也能存圖
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd

ROOT = Path(__file__).parent.parent
RESULTS_PATH = ROOT / "eval" / "eval_results.json"
OUTPUT_PATH = ROOT / "eval" / "eval_report.png"

# 嘗試設定中文字型（Windows）
def _set_chinese_font():
    candidates = [
        "Microsoft JhengHei", "Microsoft YaHei",
        "SimHei", "PingFang TC", "Noto Sans CJK TC",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            return
    plt.rcParams["font.family"] = "DejaVu Sans"  # fallback，中文可能顯示為方塊


def plot(results_path: Path = RESULTS_PATH, output_path: Path = OUTPUT_PATH):
    _set_chinese_font()
    plt.rcParams["axes.unicode_minus"] = False

    data = json.loads(results_path.read_text(encoding="utf-8"))
    df = pd.json_normalize(data)
    df = df.rename(columns={
        "scores.completeness": "completeness",
        "scores.accuracy": "accuracy",
        "scores.format_ok": "format_ok",
        "scores.coverage_rate": "coverage_rate",
    })

    metrics = ["completeness", "accuracy", "format_ok", "coverage_rate"]
    labels = ["完整度 (0-5)", "準確性 (0-5)", "格式正確率 (0-1)", "key_points 涵蓋率 (0-1)"]
    types = df["type"].unique()
    versions = sorted(df["prompt_version"].unique())
    colors = {"v1": "#4C72B0", "v2": "#DD8452", "v3": "#55A868"}

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Prompt v1 vs v2 評估報告", fontsize=16, fontweight="bold", y=1.01)

    for ax, metric, label in zip(axes.flat, metrics, labels):
        avg = (
            df.groupby(["type", "prompt_version"])[metric]
            .mean()
            .unstack("prompt_version")
            .reindex(columns=versions)
        )
        x = range(len(avg))
        width = 0.35
        for i, version in enumerate(versions):
            offset = (i - 0.5) * width
            bars = ax.bar(
                [xi + offset for xi in x],
                avg[version],
                width,
                label=f"Prompt {version}",
                color=colors[version],
                alpha=0.85,
            )
            for bar in bars:
                h = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    h + 0.02,
                    f"{h:.2f}",
                    ha="center", va="bottom", fontsize=8,
                )

        ax.set_title(label, fontsize=12)
        ax.set_xticks(list(x))
        ax.set_xticklabels(avg.index, fontsize=9)
        ax.set_ylim(0, max(5.5 if "0-5" in label else 1.2, avg.values.max() * 1.2))
        ax.legend(fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    # 總分雷達圖（正規化至 0-1）
    # 改用最後一個 subplot 顯示各指標平均總表
    ax = axes.flat[-1]
    ax.clear()

    summary = df.groupby("prompt_version")[metrics].mean()
    norm = summary.copy()
    norm["completeness"] /= 5
    norm["accuracy"] /= 5

    norm_T = norm.T
    norm_T.index = labels
    norm_T.plot(kind="barh", ax=ax, color=[colors[v] for v in norm_T.columns], alpha=0.85)
    ax.set_xlim(0, 1.1)
    ax.set_title("各指標平均（正規化至 0-1）", fontsize=12)
    ax.set_xlabel("分數", fontsize=9)
    ax.legend(title="Prompt", fontsize=9)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    for bar_container in ax.containers:
        ax.bar_label(bar_container, fmt="%.2f", padding=3, fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"圖表已儲存至 {output_path}")


if __name__ == "__main__":
    if not RESULTS_PATH.exists():
        print(f"找不到 {RESULTS_PATH}，請先執行 python eval/run_eval.py")
        sys.exit(1)
    plot()
