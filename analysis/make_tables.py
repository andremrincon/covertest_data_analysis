#!/usr/bin/env python3
"""
make_tables.py -- Reproduce Tables 3, 4, and 5 of the ANOMTOOL paper
(AST 2027) from the consolidated CSVs produced by extract.py.

Usage:
    python3 make_tables.py [--data DIR] [--out DIR]

Reads:
    <DATA>/executions.csv   (one row per execution, 270 rows)
    <DATA>/steps.csv        (one row per generation stage, 810 rows)

Writes, to <OUT>:
    table3_per_service.csv   / .tex
    table4_stage_chain.csv   / .tex
    table5_position.csv      / .tex
and prints all three to stdout for a quick sanity check against the PDF.
"""
import argparse
import os

import numpy as np
import pandas as pd
from scipy import stats


def paired_cohens_dz(before, after):
    d = np.asarray(after) - np.asarray(before)
    return d.mean() / d.std(ddof=1)


def to_latex_rows(df, cols, fmt):
    lines = []
    for _, row in df.iterrows():
        cells = [fmt[c](row[c]) if c in fmt else str(row[c]) for c in cols]
        lines.append(" & ".join(cells) + r" \\")
    return "\n".join(lines)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=os.path.join(here, "data"))
    ap.add_argument("--out", default=os.path.join(here, "tables"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    E = pd.read_csv(os.path.join(args.data, "executions.csv"))
    S = pd.read_csv(os.path.join(args.data, "steps.csv"))
    assert len(E) == 270, f"expected 270 executions, found {len(E)}"
    assert len(S) == 810, f"expected 810 steps, found {len(S)}"

    # =====================================================================
    # Table 3 -- Instruction coverage before (T0) and after the three
    # stages, per service (mean over all orderings, seeds, and runs).
    # =====================================================================
    t3 = E.groupby("project").agg(T0=("T0", "mean"), Final=("C3", "mean"))
    t3["Gain"] = t3["Final"] - t3["T0"]
    t3 = t3.reindex(["features-service", "ncs", "restcountries",
                      "scs", "spring-actuator-demo"])
    pooled = pd.DataFrame(
        {"T0": [E.T0.mean()], "Final": [E.C3.mean()],
         "Gain": [(E.C3 - E.T0).mean()]},
        index=["Pooled"])
    t3 = pd.concat([t3, pooled])
    t3.to_csv(os.path.join(args.out, "table3_per_service.csv"))

    print("=" * 70)
    print("Table 3 -- Instruction coverage before (T0) and after, per service")
    print("=" * 70)
    print(t3.round(2).to_string())

    with open(os.path.join(args.out, "table3_per_service.tex"), "w") as f:
        f.write(to_latex_rows(
            t3.reset_index().rename(columns={"index": "Service"}),
            ["Service", "T0", "Final", "Gain"],
            fmt={"T0": lambda v: f"{v:.2f}", "Final": lambda v: f"{v:.2f}",
                 "Gain": lambda v: f"{v:.2f}"}))

    # =====================================================================
    # Table 4 -- Stage-wise coverage over the 270 executions.
    # =====================================================================
    rows = []
    for label, before, after in [
        ("$T_0 \\rightarrow C_1$ (1st model)", E.T0, E.C1),
        ("$C_1 \\rightarrow C_2$ (2nd model)", E.C1, E.C2),
        ("$C_2 \\rightarrow C_3$ (3rd model)", E.C2, E.C3),
        ("$T_0 \\rightarrow C_3$ (full)", E.T0, E.C3),
    ]:
        rows.append(dict(Transition=label, Before=before.mean(),
                          After=after.mean(), Gain=(after - before).mean()))
    t4 = pd.DataFrame(rows)
    t4.to_csv(os.path.join(args.out, "table4_stage_chain.csv"), index=False)

    print("\n" + "=" * 70)
    print("Table 4 -- Stage-wise coverage over the 270 executions")
    print("=" * 70)
    print(t4.round(2).to_string(index=False))

    check = (t4.loc[0, "Gain"] + t4.loc[1, "Gain"] + t4.loc[2, "Gain"])
    print(f"(sanity check: sum of the three incremental rows = {check:.4f}, "
          f"full-chain gain = {t4.loc[3, 'Gain']:.4f})")

    with open(os.path.join(args.out, "table4_stage_chain.tex"), "w") as f:
        f.write(to_latex_rows(
            t4, ["Transition", "Before", "After", "Gain"],
            fmt={"Before": lambda v: f"{v:.2f}", "After": lambda v: f"{v:.2f}",
                 "Gain": lambda v: f"{v:.2f}"}))

    # Optional companion statistics (paired Wilcoxon + effect size),
    # reported in the text around Table 4 / Section 5.3.
    print("\n--- companion statistics (paired Wilcoxon signed-rank, dz) ---")
    for label, before, after in [
        ("T0->C1", E.T0, E.C1), ("C1->C2", E.C1, E.C2),
        ("C2->C3", E.C2, E.C3), ("C1->C3", E.C1, E.C3),
    ]:
        _, p = stats.wilcoxon(after, before)
        dz = paired_cohens_dz(before, after)
        print(f"  {label:8s} mean diff = {(after - before).mean():7.4f}  "
              f"p = {p:.3g}  dz = {dz:.3f}")

    # =====================================================================
    # Table 5 -- Marginal coverage gain by pipeline position (Figure 4),
    # aggregated over the 270 executions / 810 steps.
    # =====================================================================
    t5 = S.groupby("position").gain.agg(["mean", "std", "sum"])
    t5["share_pct"] = t5["sum"] / t5["sum"].sum() * 100
    t5.to_csv(os.path.join(args.out, "table5_position.csv"))

    print("\n" + "=" * 70)
    print("Table/Figure 4 -- Marginal coverage gain by pipeline position")
    print("=" * 70)
    print(t5.round(2).to_string())
    print(f"(sanity check: sum of per-position means = "
          f"{t5['mean'].sum():.4f}, total pooled gain = "
          f"{(E.C3 - E.T0).mean():.4f})")

    with open(os.path.join(args.out, "table5_position.tex"), "w") as f:
        f.write(to_latex_rows(
            t5.reset_index(), ["position", "mean", "std", "share_pct"],
            fmt={"mean": lambda v: f"{v:.2f}", "std": lambda v: f"{v:.2f}",
                 "share_pct": lambda v: f"{v:.1f}"}))

    print(f"\n[make_tables] wrote CSV + TeX fragments to {args.out}")


if __name__ == "__main__":
    main()
