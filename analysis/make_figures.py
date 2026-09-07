#!/usr/bin/env python3
"""
make_figures.py -- Reproduce Figures 3 and 4 of the ANOMTOOL paper
(AST 2027) from the consolidated CSVs produced by extract.py.

Usage:
    python3 make_figures.py [--data DIR] [--out DIR]

Reads:
    <DATA>/executions.csv
    <DATA>/steps.csv

Writes, to <OUT>:
    fig03_coverage_evolution.pdf / .png
    fig04_gain_by_position.pdf   / .png
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PALETTE = ["#20808D", "#A84B2F", "#1B474D", "#FFC553", "#944454", "#848456"]

# Model order labels use the full model identifiers, matching the paper's
# LLM_MODELS_GEN examples (qwen/qwen3.7-plus, openai/gpt-5-mini, z-ai/glm-5.2).
MODEL_LABEL = {
    "qwen3.7-plus": "qwen3.7-plus", "qwen": "qwen3.7-plus",
    "gpt-5-mini": "gpt-5-mini", "gpt5mini": "gpt-5-mini",
    "glm-5.2": "glm-5.2", "glm": "glm-5.2",
}


def sequence_label(row):
    return " -> ".join(MODEL_LABEL[m] for m in
                        [row["m1"], row["m2"], row["m3"]])


def save(fig, out_dir, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out_dir, f"{name}.{ext}"),
                     bbox_inches="tight")
    plt.close(fig)
    print(f"[make_figures] wrote {name}.pdf / .png")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=os.path.join(here, "data"))
    ap.add_argument("--out", default=os.path.join(here, "figures"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": 300, "font.size": 11,
        "axes.titlesize": 13, "axes.titleweight": "bold",
        "axes.labelsize": 11, "legend.fontsize": 8.5,
        "font.family": "DejaVu Sans",
    })

    E = pd.read_csv(os.path.join(args.data, "executions.csv"))
    S = pd.read_csv(os.path.join(args.data, "steps.csv"))
    assert len(E) == 270, f"expected 270 executions, found {len(E)}"
    assert len(S) == 810, f"expected 810 steps, found {len(S)}"

    seq_labels = (E.drop_duplicates("seq_num")
                    .set_index("seq_num")
                    .apply(sequence_label, axis=1)
                    .to_dict())

    # =====================================================================
    # Figure 3 -- Coverage evolution from the baseline through the three
    # stages, one line per model ordering.
    # =====================================================================
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, (sn, g) in enumerate(E.groupby("seq_num")):
        y = [g.T0.mean(), g.C1.mean(), g.C2.mean(), g.C3.mean()]
        ax.plot([0, 1, 2, 3], y, marker="o", color=PALETTE[i - 1],
                 label=seq_labels[sn], lw=1.6, ms=5)
        ax.annotate(f"{y[3]:.1f}", (3, y[3]), textcoords="offset points",
                     xytext=(6, 0), fontsize=7, color=PALETTE[i - 1],
                     va="center")
    ax.set_xticks([0, 1, 2, 3])
    ax.set_xticklabels(["T0 (initial)", "after model 1",
                         "after model 2", "after model 3"])
    ax.set_ylabel("Mean instruction coverage (%)")
    ax.legend(title="Model order", loc="lower right")
    save(fig, args.out, "fig03_coverage_evolution")

    # =====================================================================
    # Figure 4 -- Marginal coverage gain by pipeline position, pooled over
    # the 270 executions.
    # =====================================================================
    pos = S.groupby("position").gain.agg(["mean", "std"])
    cols = ["#20808D", "#5FA3AC", "#9FC6CC"]
    fig, ax = plt.subplots(figsize=(7, 4.6))
    ax.bar([1, 2, 3], pos["mean"], yerr=pos["std"], capsize=5,
           color=cols, width=0.62)
    for xx, v in zip([1, 2, 3], pos["mean"]):
        ax.text(xx, v + 0.45, f"{v:.2f} pp", ha="center", fontsize=9)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["Model 1\n(first)", "Model 2", "Model 3\n(last)"])
    ax.set_ylabel("Mean marginal coverage gain (pp)")
    save(fig, args.out, "fig04_gain_by_position")

    total_gain = (E.C3 - E.T0).mean()
    share_pos1 = pos.loc[1, "mean"] / total_gain * 100
    print(f"[make_figures] position 1 share of total gain: {share_pos1:.1f}%")


if __name__ == "__main__":
    main()
